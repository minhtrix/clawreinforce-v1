from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass
from dataclasses import replace
from collections.abc import Callable

from clawreinforce.core.checks import run_check
from clawreinforce.core.models import GoldenCase, ProviderResult, Skill
from clawreinforce.errors import ClawError


VERIFIED_HEADING = "## Examples (verified)"
INSTRUCT_MARKER = "CLAWREINFORCE_IMPROVE_INSTRUCT"
FEWSHOT_MARKER = "CLAWREINFORCE_IMPROVE_FEWSHOT"
Executor = Callable[[str, str, str], ProviderResult]


def improve_status() -> dict[str, object]:
    return {
        "status": "loop_ready",
        "explanation": (
            "The proposal model may rewrite instructions or mine examples, but deterministic golden checks "
            "alone decide whether each candidate survives."
        ),
        "gates": [
            {
                "id": "rewrite",
                "name": "Rewrite regression gate",
                "explanation": "Accept only when the failing target turns green and every previous pass stays green.",
            },
            {
                "id": "uplift",
                "name": "Uplift gate",
                "explanation": "Accept only when mean score rises; strict mode also rejects any per-model regression.",
            },
        ],
        "orchestrator": {"available": True, "message": "Golden rewrite loop available"},
    }


@dataclass(frozen=True, slots=True)
class GateDecision:
    accepted: bool
    reason: str
    regressions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RewriteAttempt:
    number: int
    target_case: str
    accepted: bool
    reason: str
    regressions: tuple[str, ...]
    before: dict[str, bool]
    after: dict[str, bool]
    diff: str
    verified_examples: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ImproveReport:
    skill: str
    tier: str
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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def degenerate_case(case: GoldenCase) -> bool:
    kind, value = case.check.kind, case.check.value
    if not case.input.strip() or kind not in {"equals", "contains", "not_contains", "regex", "property", "exec", "task", "agent"}:
        return True
    if kind in {"contains", "not_contains", "regex"} and str(value or "") in {"", ".*", "^.*$"}:
        return True
    return False


def gate_rewrite(before: dict[str, bool], after: dict[str, bool], target_case: str) -> GateDecision:
    if target_case not in before or target_case not in after:
        return GateDecision(False, "target case is missing from evaluation")
    regressions = tuple(case_id for case_id, passed in before.items() if passed and not after.get(case_id, False))
    if regressions:
        return GateDecision(False, "previously-green cases regressed", regressions)
    if before[target_case]:
        return GateDecision(False, "target case was already green")
    if not after[target_case]:
        return GateDecision(False, "target case is still failing")
    return GateDecision(True, "target turned green and no prior pass regressed")


def uplift_gate(before: dict[str, float], after: dict[str, float], *, strict: bool = False, target_score: float | None = None) -> GateDecision:
    shared = sorted(set(before) & set(after))
    if not shared:
        return GateDecision(False, "no shared model coverage")
    regressions = tuple(model for model in shared if after[model] < before[model])
    if strict and regressions:
        return GateDecision(False, "strict per-model regression gate failed", regressions)
    old_mean = sum(before[model] for model in shared) / len(shared)
    new_mean = sum(after[model] for model in shared) / len(shared)
    if new_mean <= old_mean:
        return GateDecision(False, "mean score did not rise", regressions)
    if target_score is not None and new_mean < target_score:
        return GateDecision(True, f"accepted; target {target_score:.3f} not reached")
    return GateDecision(True, "mean score rose")


def verified_examples(body: str, cases: list[GoldenCase], outputs: dict[str, str]) -> tuple[str, list[str]]:
    existing = {
        case_input.strip(): output.strip()
        for case_input, output in re.findall(
            r"- Input: (.*?)\n  Output: (.*?)(?=\n- Input:|\Z)", body, flags=re.DOTALL
        )
    }
    verified: list[str] = []
    for case in cases:
        output = outputs.get(case.id, existing.get(case.input.strip()))
        if output is not None and run_check(case.check, output).passed:
            verified.append(f"- Input: {case.input}\n  Output: {output}")
    base = body.split(VERIFIED_HEADING, 1)[0].rstrip()
    if not verified:
        return base, []
    return base + "\n\n" + VERIFIED_HEADING + "\n\n" + "\n".join(verified), verified


def improve_skill(
    skill: Skill,
    tier: str,
    strategy: str,
    max_rewrites: int,
    executor: Executor,
) -> ImproveReport:
    """Propose and gate skill-body rewrites without mutating the skill on disk."""
    _validate_run(skill, tier, strategy, max_rewrites)
    initial = _grade(skill, tier, executor)
    if all(initial.values()):
        return _report(skill, tier, strategy, "unchanged", False, "all golden cases already pass", initial, initial, skill.body, ())

    working = skill
    outcomes = initial
    attempts: list[RewriteAttempt] = []
    accepted_any = False
    for number in range(1, max_rewrites + 1):
        failing = [case for case in working.cases if not outcomes[case.id]]
        if not failing:
            break
        target = failing[0]
        if strategy == "instruct":
            candidate_body, examples = _instruct_body(working, failing, tier, executor), []
        else:
            candidate_body, examples = _fewshot_body(working, failing, tier, executor)
        candidate = replace(working, body=candidate_body)
        after = _grade(candidate, tier, executor)
        decision = gate_rewrite(outcomes, after, target.id)
        attempts.append(
            RewriteAttempt(
                number,
                target.id,
                decision.accepted,
                decision.reason,
                decision.regressions,
                dict(outcomes),
                dict(after),
                _diff(working.body, candidate_body),
                tuple(examples),
            )
        )
        if decision.accepted:
            working, outcomes, accepted_any = candidate, after, True

    remaining = [case_id for case_id, passed in outcomes.items() if not passed]
    if not remaining:
        status, reason = "completed", "all golden cases pass"
    elif accepted_any:
        status, reason = "partial", f"max rewrites reached; still failing: {', '.join(remaining)}"
    else:
        status, reason = "rejected", attempts[-1].reason
    return _report(skill, tier, strategy, status, accepted_any, reason, initial, outcomes, working.body, tuple(attempts))


def _validate_run(skill: Skill, tier: str, strategy: str, max_rewrites: int) -> None:
    if not skill.cases:
        raise ClawError("improve.no_cases", "validation", "skill has no golden cases", skill=skill.name)
    if ":" not in tier:
        raise ClawError("tier.invalid", "validation", "tier must be provider:model", tier=tier)
    if strategy not in {"instruct", "fewshot"}:
        raise ClawError("improve.strategy", "validation", "strategy must be instruct or fewshot", strategy=strategy)
    if max_rewrites < 1:
        raise ClawError("improve.max_rewrites", "validation", "max rewrites must be at least 1", max_rewrites=max_rewrites)


def _grade(skill: Skill, tier: str, executor: Executor) -> dict[str, bool]:
    outcomes: dict[str, bool] = {}
    system = (
        "Follow the supplied agent skill. Return only the task artifact; do not explain your reasoning."
        f"\n\n<skill>\n{skill.body}\n</skill>"
    )
    for case in skill.cases:
        output = _completed(executor(tier, system, case.input))
        outcomes[case.id] = run_check(case.check, output).passed
    return outcomes


def _instruct_body(skill: Skill, failing: list[GoldenCase], tier: str, executor: Executor) -> str:
    cases = "\n".join(f"- {case.id}: input={case.input!r}; check={case.check.kind} {case.check.value!r}" for case in failing)
    system = (
        f"{INSTRUCT_MARKER}\nRewrite the skill body so the failing deterministic cases pass without weakening existing behavior. "
        "Return only the complete replacement Markdown body, with no frontmatter or code fence."
        f"\n\n<skill>\n{skill.body}\n</skill>"
    )
    return _clean_body(_completed(executor(tier, system, cases)))


def _fewshot_body(skill: Skill, failing: list[GoldenCase], tier: str, executor: Executor) -> tuple[str, list[str]]:
    outputs: dict[str, str] = {}
    for case in failing:
        system = (
            f"{FEWSHOT_MARKER}\nFollow the supplied skill and return only a candidate output for the failing case."
            f"\n\n<skill>\n{skill.body}\n</skill>"
        )
        outputs[case.id] = _completed(executor(tier, system, case.input))
    return verified_examples(skill.body, list(skill.cases), outputs)


def _completed(result: ProviderResult) -> str:
    if result.status == "completed" and result.output is not None:
        return result.output
    detail = result.error or {
        "code": "provider.unavailable",
        "kind": "unavailable",
        "message": "provider did not return a completed output",
        "context": {},
    }
    raise ClawError(
        str(detail.get("code", "provider.unavailable")),
        str(detail.get("kind", "unavailable")),
        str(detail.get("message", "provider did not return a completed output")),
        **dict(detail.get("context") or {}),
    )


def _clean_body(value: str) -> str:
    body = value.strip()
    if body.startswith("```") and body.endswith("```"):
        lines = body.splitlines()
        body = "\n".join(lines[1:-1]).strip()
    return body


def _diff(before: str, after: str) -> str:
    return "\n".join(
        difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile="SKILL.md:before", tofile="SKILL.md:after", lineterm="")
    )


def _report(
    skill: Skill,
    tier: str,
    strategy: str,
    status: str,
    accepted: bool,
    reason: str,
    before: dict[str, bool],
    after: dict[str, bool],
    body: str,
    attempts: tuple[RewriteAttempt, ...],
) -> ImproveReport:
    return ImproveReport(
        skill.name,
        tier,
        strategy,
        status,
        accepted,
        reason,
        dict(before),
        dict(after),
        skill.body,
        body,
        _diff(skill.body, body),
        attempts,
    )
