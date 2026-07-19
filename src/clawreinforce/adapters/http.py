from __future__ import annotations

import json
import mimetypes
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from clawreinforce.adapters.providers import ProviderHub
from clawreinforce.adapters.run_broker import RunBroker, RunState
from clawreinforce.adapters.http_verify import (
    certify_source,
    check_certificate,
    guard_source,
    scan_source,
    skill_catalog,
)
from clawreinforce.core.arena import load_task, run_bench, task_health
from clawreinforce.core.improve import gate_rewrite, improve_status, uplift_gate
from clawreinforce.core.ledger import append_event, read_events
from clawreinforce.core.task_source import fetched_task
from clawreinforce.errors import ClawError


class AppState:
    def __init__(self, project_root: Path, web_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.web_root = web_root.resolve()
        self.providers = ProviderHub(self.project_root)
        self.runs = RunBroker()
        self._model_cache: tuple[float, dict[str, Any]] | None = None

    def model_catalog(self, refresh: bool = False) -> dict[str, Any]:
        if self._model_cache and not refresh and time.monotonic() - self._model_cache[0] < 300:
            return self._model_cache[1]
        providers = self.providers.status()
        models: list[dict[str, str]] = []
        for row in providers:
            row["models"] = []
            if row["provider"] == "fixture":
                row["models"] = ["echo", "upper-if-skilled"]
                models.extend(
                    {"provider": "fixture", "model": model, "tier": f"fixture:{model}"}
                    for model in row["models"]
                )
                continue
            if not row["configured"]:
                continue
            result = self.providers.discover(row["provider"])
            if result.status == "completed" and result.output:
                row["models"] = json.loads(result.output)
                models.extend({"provider": row["provider"], "model": model, "tier": f"{row['provider']}:{model}"} for model in row["models"])
            else:
                row["last_error"] = result.error
        preset = next((model["tier"] for model in models if model["provider"] == "ollama-cloud"), "fixture:echo")
        payload = {"providers": providers, "models": models, "preset": preset}
        self._model_cache = (time.monotonic(), payload)
        return payload

    def start_bench(self, payload: dict[str, Any]) -> RunState:
        public_id = uuid.uuid4().hex[:12]
        state = self.runs.create(public_id)

        def worker() -> None:
            try:
                with fetched_skill(str(payload["skill"])) as skill_root, fetched_task(str(payload["task"])) as task_root:
                    skill = load_skill(skill_root)
                    task = load_task(task_root)
                    tiers = list(payload.get("tiers") or [self.model_catalog()["preset"]])
                    trials = int(payload.get("trials", 1))

                    def emit(event: dict[str, Any]) -> None:
                        state.emit({**event, "run_id": public_id})

                    report = run_bench(
                        task,
                        skill,
                        tiers,
                        trials,
                        self.providers.execute,
                        emit=emit,
                        is_cancelled=lambda: state.cancelled,
                        run_id=public_id,
                    )
                store = self.project_root / ".clawreinforce" / "bench"
                store.mkdir(parents=True, exist_ok=True)
                report_path = store / f"{report.run_id}.json"
                report_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
                append_event(self.project_root, "bench-runs", {"run_id": report.run_id, "report_path": str(report_path), "summary": report.summary})
            except Exception as exc:
                error = _error(exc)
                state.emit({"type": "run_failed", "run_id": public_id, "error": error})

        threading.Thread(target=worker, name=f"bench-{public_id}", daemon=True).start()
        return state


def _error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ClawError):
        return exc.detail.to_dict()
    return {"code": "http.failed", "kind": "runtime", "message": str(exc), "context": {}}


def make_handler(app: AppState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "clawreinforce/0.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"http {self.address_string()} {fmt % args}")

        def _json(self, value: Any, status: int = 200) -> None:
            data = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                if path == "/api/health":
                    self._json({"status": "ok", "product": "clawreinforce"})
                elif path == "/api/skills":
                    self._json(skill_catalog(app.project_root))
                elif path == "/api/improve/status":
                    self._json(improve_status())
                elif path == "/api/models":
                    self._json(app.model_catalog("refresh=1" in parsed.query))
                elif path.startswith("/api/runs/") and path.endswith("/events"):
                    self._sse(path.split("/")[3])
                elif path.startswith("/api/runs/"):
                    state = app.runs.get(path.split("/")[3])
                    self._json({"events": state.events, "finished": state.finished, "cancelled": state.cancelled} if state else {"error": "not found"}, 200 if state else 404)
                else:
                    self._static(path)
            except Exception as exc:
                self._json({"error": _error(exc)}, 500)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                payload = self._body()
                if path == "/api/scan":
                    self._json(scan_source(app.project_root, str(payload.get("path", ""))))
                elif path == "/api/certify":
                    self._json(
                        certify_source(
                            app.project_root,
                            str(payload.get("source", "")),
                            list(payload.get("tiers") or []),
                            int(payload.get("samples", 1)),
                            app.providers.execute,
                        )
                    )
                elif path == "/api/certificates/verify":
                    self._json(check_certificate(payload))
                elif path == "/api/guard":
                    self._json(
                        guard_source(
                            app.project_root,
                            str(payload.get("source", "")),
                            list(payload.get("tiers") or ["openai:gpt-5.6-sol"]),
                            int(payload.get("samples", 1)),
                            app.providers.execute,
                        )
                    )
                elif path == "/api/bench":
                    state = app.start_bench(payload)
                    self._json({"run_id": state.run_id}, HTTPStatus.ACCEPTED)
                elif path.startswith("/api/runs/") and path.endswith("/cancel"):
                    run_id = path.split("/")[3]
                    self._json({"cancelled": app.runs.cancel(run_id)}, 200 if app.runs.get(run_id) else 404)
                elif path == "/api/tasks/health":
                    with fetched_task(str(payload["path"])) as fetched:
                        task = load_task(fetched)
                        self._json({"task": task.name, "source": task.source, "difficulty": task.difficulty, **task_health(task)})
                elif path == "/api/improve/gate":
                    decision = gate_rewrite(dict(payload["before"]), dict(payload["after"]), str(payload["target_case"]))
                    self._json(decision.to_dict())
                elif path == "/api/improve/uplift-gate":
                    decision = uplift_gate(dict(payload["before"]), dict(payload["after"]), strict=bool(payload.get("strict")))
                    self._json(decision.to_dict())
                elif path == "/api/history":
                    self._json({"bench_runs": read_events(Path(payload["skill"]), "bench-runs")})
                else:
                    self._json({"error": {"code": "route.not_found"}}, 404)
            except Exception as exc:
                self._json({"error": _error(exc)}, 400)

        def _sse(self, run_id: str) -> None:
            state = app.runs.get(run_id)
            if state is None:
                self._json({"error": {"code": "run.not_found"}}, 404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            index = 0
            while True:
                with state.condition:
                    state.condition.wait_for(lambda: index < len(state.events) or state.finished, timeout=15)
                    pending = state.events[index:]
                for event in pending:
                    data = json.dumps(event, ensure_ascii=False)
                    self.wfile.write(f"event: {event.get('type', 'message')}\ndata: {data}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    index += 1
                if state.finished and index >= len(state.events):
                    return
                if not pending:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()

        def _static(self, request_path: str) -> None:
            relative = "index.html" if request_path == "/" else request_path.lstrip("/")
            path = (app.web_root / relative).resolve()
            if app.web_root not in path.parents and path != app.web_root:
                self._json({"error": {"code": "static.unsafe_path"}}, 400)
                return
            if not path.is_file():
                path = app.web_root / "index.html"
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def serve(project_root: Path, host: str = "127.0.0.1", port: int = 8788) -> None:
    web_root = Path(__file__).parents[3] / "web"
    app = AppState(project_root, web_root)
    server = ThreadingHTTPServer((host, port), make_handler(app))
    print(f"clawreinforce listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
