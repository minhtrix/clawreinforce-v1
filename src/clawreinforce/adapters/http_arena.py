from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from clawreinforce.adapters.providers import ProviderHub
from clawreinforce.adapters.run_broker import RunBroker, RunState
from clawreinforce.core.arena import BenchReport, load_task, run_bench, task_health
from clawreinforce.core.exports import export_csv, export_png
from clawreinforce.core.fetch import fetched_skill
from clawreinforce.core.ledger import append_event
from clawreinforce.core.skill import load_skill
from clawreinforce.core.task_source import fetched_task
from clawreinforce.errors import ClawError


REMOTE_TASKS = (
    ("court-form-filling", "easy"),
    ("edit-pdf", "medium"),
    ("3d-scan-calc", "hard"),
)


def task_catalog(project_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    examples = project_root / "examples"
    if examples.is_dir():
        for task_file in sorted(examples.glob("*/task.json")):
            task = load_task(task_file.parent)
            rows.append(
                {
                    "name": task.name,
                    "source": task_file.parent.relative_to(project_root).as_posix(),
                    "difficulty": task.difficulty or "fixture",
                    "category": task.category or "smoke-test",
                    "gradeable": True,
                }
            )
    rows.extend(
        {
            "name": slug,
            "source": f"https://github.com/benchflow-ai/skillsbench/tree/main/tasks/{slug}",
            "difficulty": difficulty,
            "gradeable": False,
        }
        for slug, difficulty in REMOTE_TASKS
    )
    return {"tasks": rows}


class BenchManager:
    def __init__(self, project_root: Path, providers: ProviderHub, runs: RunBroker) -> None:
        self.project_root = project_root
        self.providers = providers
        self.runs = runs
        self._reports: dict[str, BenchReport] = {}
        self._lock = threading.Lock()

    def start(self, payload: dict[str, Any], default_tier: str) -> RunState:
        skill_source = str(payload.get("skill", "")).strip()
        task_source = str(payload.get("task", "")).strip()
        tiers = [str(tier).strip() for tier in payload.get("tiers") or [default_tier]]
        trials = int(payload.get("trials", 1))
        if not skill_source or not task_source:
            raise ClawError("arena.source_missing", "validation", "select both a task and a skill")
        if not tiers or any(not tier for tier in tiers):
            raise ClawError("arena.tier_missing", "validation", "select at least one provider:model tier")
        if trials < 1 or trials > 20:
            raise ClawError("arena.trials", "validation", "trials must be between 1 and 20", trials=trials)
        public_id = uuid.uuid4().hex[:12]
        state = self.runs.create(public_id)

        def worker() -> None:
            try:
                with fetched_skill(_source(self.project_root, skill_source)) as skill_root:
                    with fetched_task(_source(self.project_root, task_source)) as task_root:
                        skill = load_skill(skill_root)
                        task = load_task(task_root)

                        def emit(event: dict[str, Any]) -> None:
                            if event.get("report"):
                                with self._lock:
                                    self._reports[public_id] = BenchReport.from_dict(event["report"])
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
                self._persist(report)
            except Exception as exc:
                state.emit({"type": "run_failed", "run_id": public_id, "error": _error(exc)})

        threading.Thread(target=worker, name=f"bench-{public_id}", daemon=True).start()
        return state

    def export(self, run_id: str, kind: str) -> tuple[bytes, str, str]:
        with self._lock:
            report = self._reports.get(run_id)
        if report is None:
            state = self.runs.get(run_id)
            if state and not state.finished:
                raise ClawError("arena.export_pending", "unavailable", "run is still in progress", run_id=run_id)
            raise ClawError("arena.run_not_found", "not_found", "completed run was not found", run_id=run_id)
        store = self.project_root / ".clawreinforce" / "bench"
        if kind == "csv":
            path = export_csv(report, store / f"{run_id}.csv")
            return path.read_bytes(), "text/csv; charset=utf-8", f"clawreinforce-{run_id}.csv"
        if kind == "png":
            path = export_png(report, store / f"{run_id}.png")
            return path.read_bytes(), "image/png", f"clawreinforce-{run_id}.png"
        raise ClawError("arena.export_kind", "validation", "export kind must be csv or png", kind=kind)

    def health(self, source: str) -> dict[str, Any]:
        with fetched_task(_source(self.project_root, source)) as fetched:
            task = load_task(fetched)
            return {"task": task.name, "source": task.source, "difficulty": task.difficulty, **task_health(task)}

    def _persist(self, report: BenchReport) -> None:
        store = self.project_root / ".clawreinforce" / "bench"
        store.mkdir(parents=True, exist_ok=True)
        report_path = store / f"{report.run_id}.json"
        report_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        append_event(
            self.project_root,
            "bench-runs",
            {"run_id": report.run_id, "report_path": str(report_path), "summary": report.summary},
        )


def _source(project_root: Path, source: str) -> str:
    candidate = (project_root / source).resolve()
    if candidate.exists() and (candidate == project_root or project_root in candidate.parents):
        return str(candidate)
    return source


def _error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ClawError):
        return exc.detail.to_dict()
    return {"code": "arena.failed", "kind": "runtime", "message": str(exc), "context": {}}
