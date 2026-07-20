from __future__ import annotations

import json
import tomllib
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from clawreinforce.core.checks import run_check
from clawreinforce.core.arena_summary import summarize_arena
from clawreinforce.core.fingerprint import skill_fingerprint
from clawreinforce.core.models import CheckSpec, ProviderResult, Skill
from clawreinforce.core.skill import parse_frontmatter
from clawreinforce.errors import ClawError


@dataclass(frozen=True, slots=True)
class ArenaTask:
    root: Path
    name: str
    prompt: str
    check: CheckSpec | None
    oracle: str | None
    source: str = "native"
    difficulty: str | None = None


@dataclass(slots=True)
class ArenaRow:
    tier: str
    trial: int
    without_skill: float | None
    with_skill: float | None
    uplift: float | None
    status: str
    reason: str | dict[str, Any] | None = None
    last_error: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


@dataclass(slots=True)
class BenchReport:
    run_id: str
    created_at: str
    task: str
    skill: str
    fingerprint: str
    rows: list[ArenaRow]
    summary: dict[str, Any]
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BenchReport":
        return cls(
            str(value["run_id"]),
            str(value["created_at"]),
            str(value["task"]),
            str(value["skill"]),
            str(value["fingerprint"]),
            [ArenaRow(**row) for row in value["rows"]],
            dict(value["summary"]),
            bool(value.get("cancelled", False)),
        )


Executor = Callable[[str, str, str], ProviderResult]
EventSink = Callable[[dict[str, Any]], None]
CancelCheck = Callable[[], bool]


def load_task(path: str | Path) -> ArenaTask:
    requested = Path(path).resolve()
    task_file = requested / "task.json" if requested.is_dir() else requested
    if task_file.is_file() and task_file.name == "task.json":
        try:
            raw = json.loads(task_file.read_text(encoding="utf-8"))
            check = raw["check"]
            return ArenaTask(
                task_file.parent,
                str(raw["name"]),
                str(raw["prompt"]),
                CheckSpec(str(check["kind"]), check.get("value"), dict(check.get("options", {}))),
                str(raw["oracle"]),
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ClawError("task.invalid", "validation", str(exc), path=str(task_file)) from exc
    root = requested if requested.is_dir() else requested.parent
    instruction = next((root / name for name in ("task.md", "instruction.md") if (root / name).is_file()), None)
    if instruction is None:
        raise ClawError("task.missing", "not_found", "task.json, task.md, or instruction.md was not found", path=str(requested))
    frontmatter, prompt = parse_frontmatter(instruction.read_text(encoding="utf-8"))
    title = next((line[2:].strip() for line in prompt.splitlines() if line.startswith("# ")), root.name)
    difficulty = frontmatter.get("difficulty")
    metadata = root / "task.toml"
    if metadata.is_file():
        try:
            difficulty = tomllib.loads(metadata.read_text(encoding="utf-8")).get("metadata", {}).get("difficulty") or difficulty
        except (OSError, tomllib.TOMLDecodeError):
            difficulty = None
    return ArenaTask(root, title, prompt, None, None, "skillsbench", str(difficulty) if difficulty else None)


def task_health(task: ArenaTask) -> dict[str, Any]:
    if task.check is None:
        return {"healthy": None, "gradeable": False, "reason": "external SkillsBench verifier is not executed by this lightweight runner", "check": None}
    result = run_check(task.check, task.oracle)
    return {"healthy": result.passed, "gradeable": True, "reason": result.message, "check": asdict(result)}


def _phase(executor: Executor, tier: str, system: str, prompt: str, check: CheckSpec | None) -> tuple[float | None, ProviderResult]:
    response = executor(tier, system, prompt)
    if response.status != "completed" or response.output is None:
        return None, response
    return (None if check is None else (1.0 if run_check(check, response.output).passed else 0.0)), response


def _known_sum(values: list[float | int | None]) -> float | int | None:
    return sum(value for value in values if value is not None) if values and all(value is not None for value in values) else None


def _row_reason(
    task: ArenaTask,
    responses: list[ProviderResult],
    baseline: float | None,
    equipped: float | None,
) -> str | dict[str, Any] | None:
    if baseline is not None and equipped is not None:
        return None
    errors = [response.error for response in responses if response.error]
    if errors:
        return errors[-1]
    if task.check is None and all(response.status == "completed" for response in responses):
        return "ungraded: this task ships a container verifier the light runner does not execute — use a native task"
    incomplete = next((response for response in responses if response.status != "completed" or response.output is None), None)
    return {
        "code": "provider.incomplete",
        "kind": "unavailable",
        "message": "provider returned no gradeable output",
        "context": {"status": incomplete.status if incomplete else "unknown"},
    }


def run_bench(
    task: ArenaTask,
    skill: Skill,
    tiers: list[str],
    trials: int,
    executor: Executor,
    *,
    emit: EventSink | None = None,
    is_cancelled: CancelCheck | None = None,
    run_id: str | None = None,
) -> BenchReport:
    emit = emit or (lambda event: None)
    is_cancelled = is_cancelled or (lambda: False)
    run_id = run_id or uuid.uuid4().hex[:12]
    rows: list[ArenaRow] = []
    total = len(tiers) * trials
    emit({"type": "run_started", "run_id": run_id, "total": total})
    cancelled = False
    for tier in tiers:
        for trial in range(1, trials + 1):
            if is_cancelled():
                cancelled = True
                break
            baseline, base_response = _phase(executor, tier, "Return only the requested artifact.", task.prompt, task.check)
            if is_cancelled():
                cancelled = True
                break
            equipped_system = "Follow this skill and return only the requested artifact.\n\n<skill>\n" + skill.body + "\n</skill>"
            equipped, skill_response = _phase(executor, tier, equipped_system, task.prompt, task.check)
            responses = [base_response, skill_response]
            errors = [response.error for response in responses if response.error]
            reason = _row_reason(task, responses, baseline, equipped)
            row = ArenaRow(
                tier,
                trial,
                baseline,
                equipped,
                equipped - baseline if equipped is not None and baseline is not None else None,
                "ungraded" if task.check is None and all(response.status == "completed" for response in responses) else ("completed" if baseline is not None and equipped is not None else "partial"),
                reason,
                errors[-1] if errors else None,
                _known_sum([response.input_tokens for response in responses]),
                _known_sum([response.output_tokens for response in responses]),
                _known_sum([response.cost_usd for response in responses]),
            )
            rows.append(row)
            emit({"type": "model_row", "run_id": run_id, "row": asdict(row)})
            emit({"type": "progress", "run_id": run_id, "completed": len(rows), "total": total})
        if cancelled:
            break
    summary = summarize_arena(rows, tiers, trials)
    summary.update({
        "input_tokens": _known_sum([row.input_tokens for row in rows]),
        "output_tokens": _known_sum([row.output_tokens for row in rows]),
        "cost_usd": _known_sum([row.cost_usd for row in rows]),
    })
    report = BenchReport(run_id, datetime.now(timezone.utc).isoformat(), task.name, skill.name, skill_fingerprint(skill.root), rows, summary, cancelled)
    emit({"type": "run_cancelled" if cancelled else "run_completed", "run_id": run_id, "report": report.to_dict()})
    return report
