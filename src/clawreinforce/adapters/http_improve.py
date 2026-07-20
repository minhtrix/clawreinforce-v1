from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

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
) -> dict[str, Any]:
    skill = load_skill(_local_source(project_root, source))
    gates = list(gate_tiers) if gate_tiers is not None else [tier]
    report = (
        improve_skill_models(skill, author_tier or tier, gates, strategy, max_rewrites, executor)
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
        "run_id": f"improve-{uuid4().hex[:12]}",
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


def _local_source(project_root: Path, source: str) -> Path:
    value = source.strip()
    if not value:
        raise ClawError("source.missing", "validation", "choose or enter a skill source")
    root = project_root.resolve()
    candidate = (root / value).resolve()
    if candidate != root and root not in candidate.parents:
        raise ClawError("source.outside_project", "security", "improve accepts only project-local skills")
    return candidate
