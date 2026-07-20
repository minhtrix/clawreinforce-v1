from __future__ import annotations

from pathlib import Path
from typing import Any

from clawreinforce.core.improve import Executor, improve_skill
from clawreinforce.core.improve_models import improve_skill_models
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
    report = (
        improve_skill_models(skill, author_tier or tier, gate_tiers, strategy, max_rewrites, executor)
        if gate_tiers is not None
        else improve_skill(skill, tier, strategy, max_rewrites, executor)
    )
    applied = bool(apply and report.accepted and report.diff)
    if applied:
        document = skill.file.read_text(encoding="utf-8")
        skill.file.write_text(render_skill_document(document, report.candidate_body), encoding="utf-8")
    return {**report.to_dict(), "dry_run": not apply, "applied": applied}


def _local_source(project_root: Path, source: str) -> Path:
    value = source.strip()
    if not value:
        raise ClawError("source.missing", "validation", "choose or enter a skill source")
    root = project_root.resolve()
    candidate = (root / value).resolve()
    if candidate != root and root not in candidate.parents:
        raise ClawError("source.outside_project", "security", "improve accepts only project-local skills")
    return candidate
