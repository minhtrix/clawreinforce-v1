from __future__ import annotations

from dataclasses import asdict, dataclass

from clawreinforce.core.checks import run_check
from clawreinforce.core.models import GoldenCase


VERIFIED_HEADING = "## Examples (verified)"


def improve_status() -> dict[str, object]:
    return {
        "status": "gates_ready",
        "explanation": (
            "The deterministic acceptance gates are implemented. The proposal orchestrator that would run "
            "model rewrites repeatedly is not implemented yet."
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
        "orchestrator": {"available": False, "message": "Loop lands next release"},
    }


@dataclass(frozen=True, slots=True)
class GateDecision:
    accepted: bool
    reason: str
    regressions: tuple[str, ...] = ()

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
    verified: list[str] = []
    for case in cases:
        output = outputs.get(case.id)
        if output is not None and run_check(case.check, output).passed:
            verified.append(f"- Input: {case.input}\n  Output: {output}")
    base = body.split(VERIFIED_HEADING, 1)[0].rstrip()
    if not verified:
        return base, []
    return base + "\n\n" + VERIFIED_HEADING + "\n\n" + "\n".join(verified), verified
