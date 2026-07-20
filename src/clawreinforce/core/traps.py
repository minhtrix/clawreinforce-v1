from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from clawreinforce.core.checks import run_check
from clawreinforce.core.models import CheckSpec, ProviderResult, Skill
from clawreinforce.errors import ClawError


TRAP_MARKER = "CLAWREINFORCE_ADVERSARIAL_TRAPS"
SAFE_CHECKS = {"equals", "contains", "not_contains", "regex"}
Executor = Callable[[str, str, str], ProviderResult]


def discover_traps(
    skill: Skill,
    breaker_tier: str,
    gate_tiers: list[str],
    max_traps: int,
    executor: Executor,
) -> dict[str, Any]:
    if not breaker_tier.strip():
        raise ClawError("traps.breaker", "validation", "choose one breaker model")
    gates = tuple(dict.fromkeys(tier.strip() for tier in gate_tiers if tier.strip()))
    if not gates:
        raise ClawError("traps.gates", "validation", "choose at least one gate model")
    if not 1 <= max_traps <= 20:
        raise ClawError("traps.max", "validation", "max_traps must be between 1 and 20", max_traps=max_traps)

    usage: dict[str, dict[str, int]] = {}

    def tracked(tier: str, system: str, user: str) -> ProviderResult:
        result = executor(tier, system, user)
        row = usage.setdefault(tier, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
        row["calls"] += 1
        row["input_tokens"] += result.input_tokens or 0
        row["output_tokens"] += result.output_tokens or 0
        return result

    generated = tracked(breaker_tier, _breaker_prompt(skill, max_traps), "Invent adversarial cases now.")
    if generated.status != "completed" or generated.output is None:
        raise ClawError(
            "traps.breaker_failed",
            "provider",
            "breaker model did not return trap candidates",
            tier=breaker_tier,
            provider_error=generated.error,
        )
    candidates, rejected = _parse_candidates(generated.output, max_traps)
    if not candidates:
        raise ClawError(
            "traps.no_valid_candidates",
            "validation",
            "breaker returned no safe, checkable trap candidates",
            rejected=rejected,
        )

    system = f"Follow this skill exactly.\n<skill>\n{skill.body}\n</skill>"
    for candidate in candidates:
        results = []
        spec = CheckSpec(candidate["check"]["kind"], candidate["check"].get("value"))
        for tier in gates:
            response = tracked(tier, system, candidate["input"])
            if response.status != "completed" or response.output is None:
                results.append(
                    {
                        "tier": tier,
                        "status": response.status,
                        "passed": None,
                        "actual": response.output,
                        "reason": response.error or {"code": "provider.no_output", "message": "provider returned no output"},
                        "error": response.error,
                    }
                )
                continue
            check = run_check(spec, response.output)
            results.append(
                {
                    "tier": tier,
                    "status": "completed",
                    "passed": check.passed,
                    "actual": response.output,
                    "reason": check.message,
                    "error": None,
                }
            )
        candidate["results"] = results
        candidate["tears_now"] = any(row["passed"] is False for row in results)

    failures = sum(row["passed"] is False for item in candidates for row in item["results"])
    return {
        "skill": skill.name,
        "breaker_tier": breaker_tier,
        "gate_tiers": list(gates),
        "candidates_checked": len(candidates),
        "failing_candidates": sum(item["tears_now"] for item in candidates),
        "model_trap_failures": failures,
        "per_model": _per_model(candidates, gates),
        "candidates": candidates,
        "rejected_candidates": rejected,
        "usage": usage,
        "measurement_note": (
            "One completion per model × trap. Breaker rationales are hypotheses; deterministic checks and actual outputs are evidence."
        ),
    }


def freeze_traps(skill_root: Path, candidates: list[dict[str, Any]], reviewed: bool) -> dict[str, Any]:
    if not reviewed:
        raise ClawError(
            "traps.review_required",
            "validation",
            "confirm that every selected expected behavior was human-reviewed before freezing",
        )
    if not candidates:
        raise ClawError("traps.freeze_empty", "validation", "select at least one failing trap to freeze")
    path = skill_root / ".clawreinforce" / "regressions.jsonl"
    existing = _existing_regressions(path)
    added: list[str] = []
    skipped: list[dict[str, str]] = []
    lines: list[str] = []
    for index, raw in enumerate(candidates[:50]):
        candidate, reason = _candidate(raw, index)
        if reason:
            skipped.append({"candidate": str(raw.get("id", index + 1)), "reason": reason})
            continue
        if raw.get("tears_now") is not True:
            skipped.append({"candidate": candidate["id"], "reason": "candidate did not fail a measured gate model"})
            continue
        key = _case_key(candidate)
        if key in existing:
            skipped.append({"candidate": candidate["id"], "reason": "duplicate regression"})
            continue
        stored_id = "trap-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        stored = {
            "id": stored_id,
            "input": candidate["input"],
            "check": candidate["check"],
            "rationale": candidate["rationale"],
            "frozen_at": datetime.now(timezone.utc).isoformat(),
        }
        lines.append(json.dumps(stored, ensure_ascii=False))
        existing.add(key)
        added.append(stored_id)
    if lines:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            for line in lines:
                handle.write(line + "\n")
    return {
        "path": str(path),
        "added": added,
        "skipped": skipped,
        "append_only": True,
    }


def _breaker_prompt(skill: Skill, max_traps: int) -> str:
    declared = [
        {"id": case.id, "input": case.input, "check": {"kind": case.check.kind, "value": case.check.value}}
        for case in skill.cases
    ]
    return (
        f"{TRAP_MARKER}\nYou are the breaker, not the judge. Invent at most {max_traps} adversarial inputs for the "
        "supplied skill. Test only behavior the skill already promises; do not invent policy. Return only a JSON array "
        "of objects with input, check {kind,value}, and rationale. Allowed check kinds: equals, contains, not_contains, regex.\n"
        f"<skill>\n{skill.body}\n</skill>\nDeclared cases: {json.dumps(declared, ensure_ascii=False)}"
    )


def _parse_candidates(output: str, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    text = output.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ClawError("traps.invalid_json", "validation", "breaker output was not a JSON array", detail=str(exc)) from exc
    if not isinstance(raw, list):
        raise ClawError("traps.invalid_shape", "validation", "breaker output must be a JSON array")
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw[:limit]):
        candidate, reason = _candidate(item, index)
        key = _case_key(candidate) if not reason else ""
        if not reason and key in seen:
            reason = "duplicate input and check"
        if reason:
            rejected.append({"candidate": f"K{index + 1}", "reason": reason})
        else:
            seen.add(key)
            accepted.append(candidate)
    return accepted, rejected


def _candidate(raw: Any, index: int) -> tuple[dict[str, Any], str | None]:
    if not isinstance(raw, dict):
        return {}, "candidate must be an object"
    check = raw.get("check")
    if not isinstance(check, dict) or check.get("kind") not in SAFE_CHECKS:
        return {}, "check kind is missing or unsafe"
    value = check.get("value")
    candidate = {
        "id": str(raw.get("id") or f"K{index + 1}"),
        "input": str(raw.get("input", "")),
        "check": {"kind": str(check["kind"]), "value": value},
        "rationale": str(raw.get("rationale", "No breaker rationale supplied.")),
    }
    if not candidate["input"] and not (candidate["check"]["kind"] == "equals" and value == ""):
        return candidate, "input is empty without an explicit empty-output contract"
    if not isinstance(value, (str, int, float, bool)) and value is not None:
        return candidate, "check value must be scalar"
    return candidate, None


def _case_key(candidate: dict[str, Any]) -> str:
    return json.dumps(
        {"input": candidate.get("input"), "check": candidate.get("check")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _existing_regressions(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    keys: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            value = json.loads(line)
            keys.add(_case_key(value))
        except json.JSONDecodeError as exc:
            raise ClawError(
                "traps.regressions_invalid", "validation", "regressions.jsonl contains invalid JSON", line=line_number
            ) from exc
    return keys


def _per_model(candidates: list[dict[str, Any]], gates: tuple[str, ...]) -> list[dict[str, Any]]:
    rows = []
    for tier in gates:
        results = [next(row for row in item["results"] if row["tier"] == tier) for item in candidates]
        completed = [row for row in results if row["passed"] is not None]
        passed = sum(row["passed"] is True for row in completed)
        errors = [row["error"] for row in results if row["error"]]
        rows.append(
            {
                "tier": tier,
                "passed": passed,
                "total": len(candidates),
                "completed": len(completed),
                "pass_rate": passed / len(completed) if completed else None,
                "last_error": errors[-1] if errors else None,
            }
        )
    return rows
