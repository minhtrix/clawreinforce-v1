from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from clawreinforce.adapters.providers import ProviderHub
from clawreinforce.adapters.run_broker import RunBroker, RunState
from clawreinforce.core.improve import Executor, improve_skill
from clawreinforce.core.improve_evidence import enrich_improve_report, learned_patterns
from clawreinforce.core.improve_models import improve_skill_models
from clawreinforce.core.ledger import append_event, read_events
from clawreinforce.core.skill import load_skill, render_skill_document
from clawreinforce.errors import ClawError


def improve_source(
    project_root: Path,
    source: str,
    tier: str,
    strategy: str,
    max_rewrites: int,
    apply: bool,
    executor: Executor,
    *,
    author_tier: str | None = None,
    gate_tiers: list[str] | None = None,
    emit: Callable[[dict[str, Any]], None] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    skill = load_skill(_local_source(project_root, source))
    gates = list(gate_tiers) if gate_tiers is not None else [tier]
    report = (
        improve_skill_models(skill, author_tier or tier, gates, strategy, max_rewrites, executor, emit=emit)
        if gate_tiers is not None
        else improve_skill(skill, tier, strategy, max_rewrites, executor)
    )
    applied = bool(apply and report.accepted and report.diff)
    if applied:
        document = skill.file.read_text(encoding="utf-8")
        skill.file.write_text(render_skill_document(document, report.candidate_body), encoding="utf-8")
    evidence = enrich_improve_report(report.to_dict(), gates)
    event = {
        **evidence,
        "run_id": run_id or f"improve-{uuid4().hex[:12]}",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source": source.strip(),
        "output_path": skill.file.resolve().relative_to(project_root.resolve()).as_posix(),
        "dry_run": not apply,
        "applied": applied,
        "write_state": "applied" if applied else "dry_run" if not apply and report.accepted and report.diff else "unchanged",
    }
    append_event(project_root, "improve-runs", event)
    history = [row for row in read_events(project_root, "improve-runs") if row.get("source") == source.strip()][-20:]
    return {**event, "history": list(reversed(history)), "learned_patterns": learned_patterns(history)}


class ImproveManager:
    def __init__(self, project_root: Path, providers: ProviderHub, runs: RunBroker) -> None:
        self.project_root = project_root
        self.providers = providers
        self.runs = runs

    def start(self, payload: dict[str, Any]) -> RunState:
        source = str(payload.get("source", "")).strip()
        author_tier = str(payload.get("author_tier") or payload.get("tier") or "").strip()
        raw_gates = payload.get("gate_tiers")
        gates = [str(value).strip() for value in raw_gates] if isinstance(raw_gates, list) else [author_tier]
        strategy = str(payload.get("strategy", "")).strip()
        max_rewrites = int(payload.get("max_rewrites", 3))
        apply = bool(payload.get("apply"))
        if not source:
            raise ClawError("source.missing", "validation", "choose or enter a skill source")
        if not author_tier:
            raise ClawError("improve.author_tier", "validation", "choose one author model")
        if not gates or any(not tier for tier in gates):
            raise ClawError("improve.gate_tiers", "validation", "choose at least one gate model")

        public_id = f"improve-{uuid4().hex[:12]}"
        state = self.runs.create(public_id)

        def worker() -> None:
            try:
                def emit(event: dict[str, Any]) -> None:
                    state.emit({**event, "run_id": public_id})

                result = improve_source(
                    self.project_root,
                    source,
                    author_tier,
                    strategy,
                    max_rewrites,
                    apply,
                    self.providers.execute,
                    author_tier=author_tier,
                    gate_tiers=gates,
                    emit=emit,
                    run_id=public_id,
                )
                state.emit({"type": "run_completed", "run_id": public_id, "result": result})
            except Exception as exc:
                state.emit({"type": "run_failed", "run_id": public_id, "error": _error(exc)})

        threading.Thread(target=worker, name=public_id, daemon=True).start()
        return state


def _local_source(project_root: Path, source: str) -> Path:
    value = source.strip()
    if not value:
        raise ClawError("source.missing", "validation", "choose or enter a skill source")
    root = project_root.resolve()
    candidate = (root / value).resolve()
    if candidate != root and root not in candidate.parents:
        raise ClawError("source.outside_project", "security", "improve accepts only project-local skills")
    return candidate


def _error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ClawError):
        return exc.detail.to_dict()
    return {"code": "improve.failed", "kind": "runtime", "message": str(exc), "context": {}}
