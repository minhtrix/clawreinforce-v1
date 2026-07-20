from __future__ import annotations

from pathlib import Path
from typing import Any

from clawreinforce.core.fetch import fetched_skill
from clawreinforce.core.skill import load_skill
from clawreinforce.core.traps import Executor, discover_traps, freeze_traps
from clawreinforce.errors import ClawError


def discover_traps_source(
    project_root: Path,
    source: str,
    breaker_tier: str,
    gate_tiers: list[str],
    max_traps: int,
    executor: Executor,
) -> dict[str, Any]:
    resolved, local = _source(project_root, source)
    with fetched_skill(resolved) as fetched:
        result = discover_traps(load_skill(fetched), breaker_tier, gate_tiers, max_traps, executor)
    return {
        **result,
        "source": source,
        "freeze_available": local,
        "freeze_reason": None if local else "Remote skills are measured from fetched bytes. Fetch or clone locally before freezing regressions.",
    }


def freeze_traps_source(
    project_root: Path,
    source: str,
    candidates: list[dict[str, Any]],
    reviewed: bool,
) -> dict[str, Any]:
    skill = load_skill(_local_source(project_root, source))
    result = freeze_traps(skill.root, candidates, reviewed)
    path = Path(result["path"])
    result["path"] = path.relative_to(project_root.resolve()).as_posix()
    return {"skill": skill.name, **result}


def _source(project_root: Path, source: str) -> tuple[str, bool]:
    value = source.strip()
    if not value:
        raise ClawError("source.missing", "validation", "choose or enter a skill source")
    candidate = (project_root.resolve() / value).resolve()
    if candidate.exists() and (candidate == project_root.resolve() or project_root.resolve() in candidate.parents):
        return str(candidate), True
    return value, False


def _local_source(project_root: Path, source: str) -> Path:
    value = source.strip()
    if not value:
        raise ClawError("source.missing", "validation", "choose or enter a skill source")
    root = project_root.resolve()
    candidate = (root / value).resolve()
    if not candidate.exists() or (candidate != root and root not in candidate.parents):
        raise ClawError(
            "traps.freeze_local_only",
            "validation",
            "freeze accepts only a project-local skill; fetch or clone the remote skill first",
            source=source,
        )
    return candidate
