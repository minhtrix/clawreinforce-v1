from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def pass_rate(values: dict[str, bool]) -> float | None:
    return sum(values.values()) / len(values) if values else None


def enrich_improve_report(report: dict[str, Any], gate_tiers: list[str]) -> dict[str, Any]:
    models = list(report.get("per_model") or [])
    if not models:
        models = [{
            "tier": gate_tiers[0] if gate_tiers else report.get("tier", "unknown"),
            "before": dict(report.get("before") or {}),
            "after": dict(report.get("after") or {}),
        }]
    for row in models:
        row["before_pass_rate"] = pass_rate(dict(row.get("before") or {}))
        row["after_pass_rate"] = pass_rate(dict(row.get("after") or {}))

    attempts = [enrich_attempt(dict(item), gate_tiers) for item in report.get("attempts") or []]
    baseline = combined_rate(models, "before")
    best = combined_rate(models, "after")
    accepted = [item["number"] for item in attempts if item["accepted"]]
    metrics = {
        "baseline_score": baseline,
        "best_score": best,
        "gain_pp": None if baseline is None or best is None else round((best - baseline) * 100, 1),
        "accepted_iteration": accepted[-1] if accepted else None,
        "model_count": len(models),
        "check_count": sum(len(row.get("before") or {}) for row in models),
    }
    return {**report, "per_model": models, "attempts": attempts, "metrics": metrics}


def enrich_attempt(attempt: dict[str, Any], gate_tiers: list[str]) -> dict[str, Any]:
    before = dict(attempt.get("before") or {})
    after = dict(attempt.get("after") or {})
    model_rows = []
    tiers = gate_tiers or ["gate"]
    for tier in tiers:
        old = _for_tier(before, tier, len(tiers) == 1)
        new = _for_tier(after, tier, len(tiers) == 1)
        baseline, measured = pass_rate(old), pass_rate(new)
        model_rows.append({
            "tier": tier,
            "baseline_score": baseline,
            "measured_score": measured,
            "delta_pp": None if baseline is None or measured is None else round((measured - baseline) * 100, 1),
        })
    baseline, measured = pass_rate(before), pass_rate(after)
    return {
        **attempt,
        "baseline_score": baseline,
        "measured_score": measured,
        "delta_pp": None if baseline is None or measured is None else round((measured - baseline) * 100, 1),
        "diagnosis": diagnose(attempt),
        "models": model_rows,
    }


def diagnose(attempt: dict[str, Any]) -> str:
    regressions = list(attempt.get("regressions") or [])
    if attempt.get("accepted"):
        return "target fixed; zero previously-green model × case checks regressed"
    if regressions:
        return f"regression: {', '.join(regressions)}"
    if not str(attempt.get("diff") or "").strip():
        return "author returned no effective body change"
    if "still failing" in str(attempt.get("reason") or ""):
        return "candidate did not fix the selected model × case failure"
    return str(attempt.get("reason") or "candidate rejected by the rewrite gate")


def learned_patterns(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    for event in reversed(list(events)):
        for attempt in reversed(event.get("attempts") or []):
            outcome = "helped" if attempt.get("accepted") else "hurt" if attempt.get("regressions") else "no_effect"
            patterns.append({
                "outcome": outcome,
                "run_id": event.get("run_id"),
                "iteration": attempt.get("number"),
                "strategy": event.get("strategy"),
                "delta_pp": attempt.get("delta_pp"),
                "diagnosis": attempt.get("diagnosis"),
                "diff": attempt.get("diff", ""),
            })
    return patterns[:30]


def combined_rate(models: list[dict[str, Any]], key: str) -> float | None:
    values = [passed for row in models for passed in dict(row.get(key) or {}).values()]
    return sum(values) / len(values) if values else None


def _for_tier(values: dict[str, bool], tier: str, sole_tier: bool) -> dict[str, bool]:
    prefix = f"{tier} / "
    selected = {key[len(prefix):]: value for key, value in values.items() if key.startswith(prefix)}
    return selected or (values if sole_tier else {})
