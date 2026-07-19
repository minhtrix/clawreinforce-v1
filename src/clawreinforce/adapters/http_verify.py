from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from clawreinforce.core.badges import badge_svg
from clawreinforce.core.certificates import issue_certificate, load_or_create_key, verify_certificate
from clawreinforce.core.certify import Executor, certify_skill
from clawreinforce.core.fetch import fetched_skill
from clawreinforce.core.guard import guard_skill
from clawreinforce.core.scan import scan_skill
from clawreinforce.core.skill import load_skill
from clawreinforce.errors import ClawError


def skill_catalog(project_root: Path) -> dict[str, Any]:
    examples = project_root / "examples"
    rows: list[dict[str, str]] = []
    if examples.is_dir():
        for skill_file in sorted(examples.glob("*/SKILL.md")):
            skill = load_skill(skill_file.parent)
            rows.append(
                {
                    "name": skill.name,
                    "description": skill.description,
                    "source": skill_file.parent.relative_to(project_root).as_posix(),
                }
            )
    return {"skills": rows}


def scan_source(project_root: Path, source: str) -> dict[str, Any]:
    with fetched_skill(_source(project_root, source)) as fetched:
        skill = load_skill(fetched)
        return {"skill": skill.name, "findings": [asdict(row) for row in scan_skill(skill)]}


def certify_source(
    project_root: Path,
    source: str,
    tiers: list[str],
    samples: int,
    executor: Executor,
) -> dict[str, Any]:
    if samples < 1:
        raise ClawError("certify.samples", "validation", "samples must be at least 1", samples=samples)
    if not tiers or any(not tier.strip() for tier in tiers):
        raise ClawError("certify.tiers", "validation", "select at least one provider:model tier")
    with fetched_skill(_source(project_root, source)) as fetched:
        skill = load_skill(fetched)
        findings = [asdict(row) for row in scan_skill(skill)]
        report = certify_skill(skill, tiers, samples, executor)
    certificate = issue_certificate(report, load_or_create_key(project_root))
    rates = [tier.pass_rate for tier in report.tiers if tier.pass_rate is not None]
    badge = None
    if rates:
        badge = badge_svg(", ".join(tiers), sum(rates) / len(rates), gpt56=any("gpt-5.6" in tier for tier in tiers))
    return {
        "skill": report.skill,
        "findings": findings,
        "report": report.to_dict(),
        "certificate": certificate,
        "badge_svg": badge,
    }


def guard_source(
    project_root: Path,
    source: str,
    tiers: list[str],
    samples: int,
    executor: Executor,
) -> dict[str, Any]:
    with fetched_skill(_source(project_root, source)) as fetched:
        skill = load_skill(fetched)
        return {"skill": skill.name, **guard_skill(skill, tiers, samples, executor)}


def check_certificate(payload: dict[str, Any]) -> dict[str, Any]:
    certificate = payload.get("certificate")
    if not isinstance(certificate, dict):
        raise ClawError("certificate.missing", "validation", "certificate is required")
    fingerprint = payload.get("fingerprint")
    valid, message = verify_certificate(certificate, str(fingerprint) if fingerprint else None)
    return {"valid": valid, "message": message}


def _source(project_root: Path, source: str) -> str:
    value = source.strip()
    if not value:
        raise ClawError("source.missing", "validation", "choose or enter a skill source")
    candidate = (project_root / value).resolve()
    if candidate.exists() and (candidate == project_root or project_root in candidate.parents):
        return str(candidate)
    return value
