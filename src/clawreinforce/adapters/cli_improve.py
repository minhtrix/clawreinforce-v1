from __future__ import annotations

from pathlib import Path
from typing import Any

from clawreinforce.adapters.providers import ProviderHub
from clawreinforce.core.improve import improve_skill
from clawreinforce.core.skill import load_skill, render_skill_document


def improve_command(
    skill_path: str,
    tier: str,
    strategy: str,
    max_rewrites: int,
    apply: bool,
    project_root: Path,
) -> tuple[dict[str, Any], int]:
    skill = load_skill(skill_path)
    report = improve_skill(
        skill,
        tier,
        strategy,
        max_rewrites,
        ProviderHub(project_root).execute,
    )
    applied = bool(apply and report.accepted and report.diff)
    if applied:
        document = skill.file.read_text(encoding="utf-8")
        skill.file.write_text(render_skill_document(document, report.candidate_body), encoding="utf-8")
    payload = {**report.to_dict(), "dry_run": not apply, "applied": applied}
    return payload, 0 if report.status in {"completed", "unchanged"} else 2
