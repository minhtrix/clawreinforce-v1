from __future__ import annotations

from collections.abc import Callable

from clawreinforce.core.checks import run_check
from clawreinforce.core.fingerprint import skill_fingerprint
from clawreinforce.core.models import (
    CertificationReport,
    ProviderResult,
    SampleResult,
    Skill,
    TierReport,
)


Executor = Callable[[str, str, str], ProviderResult]


def _prompt(skill: Skill, case_input: str) -> tuple[str, str]:
    system = (
        "Follow the supplied agent skill. Return only the task artifact; "
        "do not explain your reasoning.\n\n<skill>\n" + skill.body + "\n</skill>"
    )
    return system, case_input


def certify_skill(
    skill: Skill,
    tiers: list[str],
    samples: int,
    executor: Executor,
    *,
    dry_run: bool = False,
) -> CertificationReport:
    expected = len(skill.cases) * samples
    tier_reports: list[TierReport] = []
    for tier in tiers:
        rows: list[SampleResult] = []
        last_error = None
        if dry_run:
            tier_reports.append(
                TierReport(tier, "dry_run", None, {"completed": 0, "expected": expected, "passed": 0}, rows)
            )
            continue
        for case in skill.cases:
            system, user = _prompt(skill, case.input)
            for sample_index in range(samples):
                response = executor(tier, system, user)
                if response.status != "completed" or response.output is None:
                    last_error = response.error
                    rows.append(SampleResult(case.id, sample_index + 1, response.status, error=response.error))
                    continue
                check = run_check(case.check, response.output)
                rows.append(SampleResult(case.id, sample_index + 1, "completed", check=check))
        completed = [row for row in rows if row.status == "completed" and row.check is not None]
        passed = sum(1 for row in completed if row.check and row.check.passed)
        pass_rate = passed / len(completed) if completed else None
        status = "completed" if len(completed) == expected else ("partial" if completed else "unavailable")
        tier_reports.append(
            TierReport(
                tier,
                status,
                pass_rate,
                {"completed": len(completed), "expected": expected, "passed": passed},
                rows,
                last_error,
            )
        )
    return CertificationReport(skill.name, skill_fingerprint(skill.root), tier_reports, dry_run)

