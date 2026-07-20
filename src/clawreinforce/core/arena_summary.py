from __future__ import annotations

import math
from typing import Any, Iterable


def summarize_arena(rows: Iterable[Any], tiers: list[str], trials: int) -> dict[str, Any]:
    values = list(rows)
    per_model = [_model_summary(tier, [row for row in values if row.tier == tier], trials) for tier in tiers]
    before = [row.without_skill for row in values if row.without_skill is not None]
    after = [row.with_skill for row in values if row.with_skill is not None]
    comparable = [row for row in per_model if row["without_rate"] is not None and row["with_rate"] is not None]
    return {
        "without_skill": _mean(before),
        "with_skill": _mean(after),
        "uplift": None if not before or not after else _mean(after) - _mean(before),
        "coverage": {
            "completed_rows": sum(row.status == "completed" for row in values),
            "expected_rows": len(tiers) * trials,
        },
        "comparison": {
            "model_count": len(tiers),
            "graded_models": len(comparable),
            "improved_models": sum(row["outcome"] == "improved" for row in comparable),
            "regressed_models": sum(row["outcome"] == "regressed" for row in comparable),
            "unchanged_models": sum(row["outcome"] == "unchanged" for row in comparable),
            "solved_without": sum(row["without_rate"] == 1 for row in comparable),
            "solved_with": sum(row["with_rate"] == 1 for row in comparable),
            "rescued_models": sum(row["without_rate"] == 0 and row["with_rate"] > 0 for row in comparable),
        },
        "reliability": {
            "k": trials,
            "without_skill": _reliability(per_model, "without", trials),
            "with_skill": _reliability(per_model, "with", trials),
        },
        "per_model": per_model,
    }


def _model_summary(tier: str, rows: list[Any], trials: int) -> dict[str, Any]:
    without = [row.without_skill for row in rows if row.without_skill is not None]
    equipped = [row.with_skill for row in rows if row.with_skill is not None]
    before_rate, after_rate = _mean(without), _mean(equipped)
    if before_rate is None or after_rate is None:
        outcome = "ungraded"
    elif after_rate > before_rate:
        outcome = "improved"
    elif after_rate < before_rate:
        outcome = "regressed"
    else:
        outcome = "unchanged"
    reason = next((row.reason or row.last_error for row in reversed(rows) if row.reason or row.last_error), None)
    return {
        "tier": tier,
        "without_rate": before_rate,
        "with_rate": after_rate,
        "uplift": None if before_rate is None or after_rate is None else after_rate - before_rate,
        "without_passed": sum(value == 1 for value in without),
        "with_passed": sum(value == 1 for value in equipped),
        "without_graded": len(without),
        "with_graded": len(equipped),
        "expected_trials": trials,
        "outcome": outcome,
        "reason": reason,
    }


def _reliability(models: list[dict[str, Any]], prefix: str, trials: int) -> dict[str, Any]:
    rate_key = f"{prefix}_rate"
    passed_key = f"{prefix}_passed"
    graded_key = f"{prefix}_graded"
    complete = [row for row in models if row[graded_key] == trials]
    passed = sum(row[passed_key] for row in models)
    graded = sum(row[graded_key] for row in models)
    return {
        "pass_at_1": passed / graded if graded else None,
        "pass_at_k": sum(row[passed_key] > 0 for row in complete) / len(complete) if complete else None,
        "pass_all_k": sum(row[passed_key] == trials for row in complete) / len(complete) if complete else None,
        "ci95": _wilson(passed, graded),
        "graded_trials": graded,
        "complete_models": len(complete),
        "mean_model_rate": _mean([row[rate_key] for row in models if row[rate_key] is not None]),
    }


def _wilson(passed: int, total: int) -> list[float] | None:
    if not total:
        return None
    z = 1.959963984540054
    rate = passed / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - spread), min(1.0, center + spread)]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
