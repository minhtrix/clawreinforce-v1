import json
import shutil
import threading
import urllib.request
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path

from clawreinforce.adapters.http import AppState, make_handler
from clawreinforce.core.ledger import append_event


ROOT = Path(__file__).parents[1]


@contextmanager
def api_server(tmp_path: Path):
    shutil.copytree(ROOT / "examples", tmp_path / "examples")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(AppState(tmp_path, ROOT / "web")))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def json_request(base: str, path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        base + path,
        data=body,
        method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def test_arena_streams_fixture_rows_and_exports(tmp_path: Path) -> None:
    with api_server(tmp_path) as base:
        catalog = json_request(base, "/api/tasks")
        uppercase = next(row for row in catalog["tasks"] if row["source"] == "examples/uppercase-task")
        assert uppercase == {
            "name": "uppercase-text",
            "source": "examples/uppercase-task",
            "difficulty": "fixture",
            "category": "smoke-test",
            "gradeable": True,
        }
        assert {row["difficulty"] for row in catalog["tasks"]} == {"fixture", "easy", "medium", "hard"}
        assert {row["category"] for row in catalog["tasks"] if row["gradeable"]} == {
            "coding",
            "operations",
            "security",
            "smoke-test",
        }

        started = json_request(
            base,
            "/api/bench",
            {
                "task": "examples/uppercase-task",
                "skill": "examples/uppercase-skill",
                "tiers": ["fixture:upper-if-skilled"],
                "trials": 2,
            },
        )
        run_id = started["run_id"]
        with urllib.request.urlopen(base + f"/api/runs/{run_id}/events", timeout=5) as response:
            events = response.read().decode()
        assert events.count("event: model_row") == 2
        assert events.index("event: model_row") < events.index("event: run_completed")

        with urllib.request.urlopen(base + f"/api/runs/{run_id}/export.csv", timeout=5) as response:
            csv_data = response.read()
            assert response.headers["Content-Disposition"].endswith(f'clawreinforce-{run_id}.csv"')
        assert csv_data.startswith(b"tier,trial,without_skill,with_skill,uplift,status")
        assert csv_data.count(b"fixture:upper-if-skilled") == 2

        with urllib.request.urlopen(base + f"/api/runs/{run_id}/export.png", timeout=5) as response:
            png_data = response.read()
            assert response.headers["Content-Type"] == "image/png"
        assert png_data.startswith(b"\x89PNG\r\n\x1a\n")


def test_history_reads_project_bench_ledger(tmp_path: Path) -> None:
    append_event(
        tmp_path,
        "bench-runs",
        {"run_id": "run-history", "summary": {"without_skill": 0.0, "with_skill": 1.0, "uplift": 1.0}},
    )
    with api_server(tmp_path) as base:
        history = json_request(base, "/api/history")
    assert history["bench_runs"][0]["run_id"] == "run-history"
    assert history["bench_runs"][0]["summary"]["uplift"] == 1.0
