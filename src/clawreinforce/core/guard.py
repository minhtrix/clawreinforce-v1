from __future__ import annotations

from dataclasses import asdict
from typing import Any

from clawreinforce.core.certify import Executor, certify_skill
from clawreinforce.core.models import Skill
from clawreinforce.core.scan import scan_skill


def guard_skill(
    skill: Skill,
    tiers: list[str],
    samples: int,
    executor: Executor,
    *,
    threshold: float = 0.8,
) -> dict[str, Any]:
    findings = scan_skill(skill)
    high = [finding for finding in findings if finding.severity == "high"]
    if high:
        return {"verdict": "reject", "reasons": ["high-severity static finding"], "findings": [asdict(row) for row in findings], "certification": None}
    if not skill.cases:
        return {"verdict": "review", "reasons": ["skill has no golden cases"], "findings": [asdict(row) for row in findings], "certification": None}
    report = certify_skill(skill, tiers, samples, executor)
    unavailable = [tier for tier in report.tiers if tier.pass_rate is None or tier.status != "completed"]
    failing = [tier for tier in report.tiers if tier.pass_rate is not None and tier.pass_rate < threshold]
    if failing:
        verdict, reasons = "reject", [f"tier below {threshold:.0%}: {tier.tier}" for tier in failing]
    elif unavailable or findings:
        verdict, reasons = "review", (["certification coverage incomplete"] if unavailable else []) + (["static findings require review"] if findings else [])
    else:
        verdict, reasons = "install", []
    return {"verdict": verdict, "reasons": reasons, "findings": [asdict(row) for row in findings], "certification": report.to_dict()}

