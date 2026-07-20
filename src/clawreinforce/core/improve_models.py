from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, replace

from clawreinforce.core.improve import (
    Executor,
    RewriteAttempt,
    _diff,
    _fewshot_body,
    _grade,
    _instruct_body,
    _validate_run,
    gate_rewrite,
)
from clawreinforce.core.models import GoldenCase, ProviderResult, Skill
from clawreinforce.errors import ClawError


Matrix = dict[str, dict[str, bool]]


@dataclass(frozen=True, slots=True)
class ModelEvidence:
    tier: str
    before: dict[str, bool]
    after: dict[str, bool]
    before_pass_rate: float | None
    after_pass_rate: float | None


@dataclass(frozen=True, slots=True)
class MultiImproveReport:
    skill: str
    tier: str
    author_tier: str
    gate_tiers: tuple[str, ...]
    strategy: str
    status: str
    accepted: bool
    reason: str
    before: dict[str, bool]
    after: dict[str, bool]
    original_body: str
    candidate_body: str
    diff: str
    attempts: tuple[RewriteAttempt, ...]
    per_model: tuple[ModelEvidence, ...]
    usage: dict[str, dict[str, int]]
    measurement_note: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def improve_skill_models(
    skill: Skill,
    author_tier: str,
    gate_tiers: list[str],
    strategy: str,
    max_rewrites: int,
    executor: Executor,
) -> MultiImproveReport:
    """Let one author propose while every selected gate model re-runs every golden case."""
    gates = _validate_models(skill, author_tier, gate_tiers, strategy, max_rewrites)
    usage: dict[str, dict[str, int]] = {}
    tracked = _tracking_executor(executor, usage)
    initial = _grade_matrix(skill, gates, tracked)
    if _all_green(initial):
        return _report(skill, author_tier, gates, strategy, "unchanged", False,
                       "all model × golden-case checks already pass", initial, initial,
                       skill.body, (), usage)

    working, outcomes = skill, initial
    attempts: list[RewriteAttempt] = []
    accepted_any = False
    for number in range(1, max_rewrites + 1):
        target_key = _first_failure(outcomes, gates, working.cases)
        if target_key is None:
            break
        failing_cases = _failing_cases(working.cases, outcomes)
        if strategy == "instruct":
            candidate_body = _instruct_body(working, failing_cases, author_tier, tracked)
            examples: list[str] = []
        else:
            candidate_body, examples = _fewshot_body(working, failing_cases, author_tier, tracked)
        candidate = replace(working, body=candidate_body)
        measured = _grade_matrix(candidate, gates, tracked)
        decision = gate_rewrite(_flatten(outcomes), _flatten(measured), target_key)
        attempts.append(
            RewriteAttempt(
                number,
                target_key,
                decision.accepted,
                decision.reason,
                decision.regressions,
                _flatten(outcomes),
                _flatten(measured),
                _diff(working.body, candidate_body),
                tuple(examples),
            )
        )
        if decision.accepted:
            working, outcomes, accepted_any = candidate, measured, True

    remaining = [key for key, passed in _flatten(outcomes).items() if not passed]
    if not remaining:
        status, reason = "completed", "all selected models pass every golden case"
    elif accepted_any:
        status, reason = "partial", f"accepted improvement; still failing: {', '.join(remaining)}"
    else:
        status = "rejected"
        reason = attempts[-1].reason if attempts else "no proposal was evaluated"
    return _report(skill, author_tier, gates, strategy, status, accepted_any, reason,
                   initial, outcomes, working.body, tuple(attempts), usage)


def _validate_models(
    skill: Skill,
    author_tier: str,
    gate_tiers: list[str],
    strategy: str,
    max_rewrites: int,
) -> tuple[str, ...]:
    _validate_run(skill, author_tier, strategy, max_rewrites)
    gates = tuple(dict.fromkeys(tier.strip() for tier in gate_tiers if tier.strip()))
    if not gates:
        raise ClawError("improve.gate_tiers", "validation", "choose at least one gate model")
    invalid = [tier for tier in gates if ":" not in tier]
    if invalid:
        raise ClawError("tier.invalid", "validation", "gate tiers must be provider:model", tiers=invalid)
    return gates


def _tracking_executor(
    executor: Executor,
    usage: dict[str, dict[str, int]],
) -> Executor:
    def tracked(tier: str, system: str, user: str) -> ProviderResult:
        result = executor(tier, system, user)
        row = usage.setdefault(tier, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
        row["calls"] += 1
        row["input_tokens"] += int(result.input_tokens or 0)
        row["output_tokens"] += int(result.output_tokens or 0)
        return result

    return tracked


def _grade_matrix(skill: Skill, gates: tuple[str, ...], executor: Executor) -> Matrix:
    return {tier: _grade(skill, tier, executor) for tier in gates}


def _flatten(matrix: Matrix) -> dict[str, bool]:
    return {f"{tier} / {case_id}": passed for tier, cases in matrix.items() for case_id, passed in cases.items()}


def _aggregate(matrix: Matrix, cases: tuple[GoldenCase, ...]) -> dict[str, bool]:
    return {case.id: all(results.get(case.id, False) for results in matrix.values()) for case in cases}


def _all_green(matrix: Matrix) -> bool:
    values = _flatten(matrix).values()
    return bool(matrix) and all(values)


def _first_failure(matrix: Matrix, gates: tuple[str, ...], cases: tuple[GoldenCase, ...]) -> str | None:
    for case in cases:
        for tier in gates:
            if not matrix[tier][case.id]:
                return f"{tier} / {case.id}"
    return None


def _failing_cases(cases: tuple[GoldenCase, ...], matrix: Matrix) -> list[GoldenCase]:
    return [case for case in cases if any(not results[case.id] for results in matrix.values())]


def _rate(values: dict[str, bool]) -> float | None:
    return sum(values.values()) / len(values) if values else None


def _report(
    skill: Skill,
    author_tier: str,
    gates: tuple[str, ...],
    strategy: str,
    status: str,
    accepted: bool,
    reason: str,
    before: Matrix,
    after: Matrix,
    body: str,
    attempts: tuple[RewriteAttempt, ...],
    usage: dict[str, dict[str, int]],
) -> MultiImproveReport:
    evidence = tuple(
        ModelEvidence(tier, dict(before[tier]), dict(after[tier]), _rate(before[tier]), _rate(after[tier]))
        for tier in gates
    )
    return MultiImproveReport(
        skill.name,
        author_tier,
        author_tier,
        gates,
        strategy,
        status,
        accepted,
        reason,
        _aggregate(before, skill.cases),
        _aggregate(after, skill.cases),
        skill.body,
        body,
        _diff(skill.body, body),
        attempts,
        evidence,
        {tier: dict(values) for tier, values in usage.items()},
        "One completion per model × case; use Arena trials for statistical confidence.",
    )
