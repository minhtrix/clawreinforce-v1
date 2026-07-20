from pathlib import Path

from clawreinforce.core.arena import ArenaTask, load_task, run_bench, task_health
from clawreinforce.core.models import ProviderResult
from clawreinforce.core.skill import load_skill


ROOT = Path(__file__).parents[1] / "examples"


def _executor(tier: str, system: str, user: str) -> ProviderResult:
    output = user.upper() if "<skill>" in system else user
    return ProviderResult("completed", output=output, input_tokens=3, output_tokens=1)


def test_oracle_health_and_uplift() -> None:
    task = load_task(ROOT / "uppercase-task")
    skill = load_skill(ROOT / "uppercase-skill")
    assert task_health(task)["healthy"]
    events: list[dict] = []
    report = run_bench(task, skill, ["fixture:upper-if-skilled"], 2, _executor, emit=events.append)
    assert report.summary["without_skill"] == 0.0
    assert report.summary["with_skill"] == 1.0
    assert report.summary["uplift"] == 1.0
    assert report.summary["coverage"] == {"completed_rows": 2, "expected_rows": 2}
    assert report.summary["comparison"] == {
        "model_count": 1,
        "graded_models": 1,
        "improved_models": 1,
        "regressed_models": 0,
        "unchanged_models": 0,
        "solved_without": 0,
        "solved_with": 1,
        "rescued_models": 1,
    }
    assert report.summary["per_model"][0] == {
        "tier": "fixture:upper-if-skilled",
        "without_rate": 0.0,
        "with_rate": 1.0,
        "uplift": 1.0,
        "without_passed": 0,
        "with_passed": 2,
        "without_graded": 2,
        "with_graded": 2,
        "expected_trials": 2,
        "outcome": "improved",
        "reason": None,
    }
    assert report.summary["reliability"]["with_skill"]["pass_at_1"] == 1.0
    assert report.summary["reliability"]["with_skill"]["pass_at_k"] == 1.0
    assert report.summary["reliability"]["with_skill"]["pass_all_k"] == 1.0
    assert report.summary["reliability"]["without_skill"]["pass_at_1"] == 0.0
    assert any(event["type"] == "model_row" for event in events)


def test_cancel_keeps_partial_results() -> None:
    task = load_task(ROOT / "uppercase-task")
    skill = load_skill(ROOT / "uppercase-skill")
    calls = 0

    def cancelled() -> bool:
        nonlocal calls
        calls += 1
        return calls > 2

    report = run_bench(task, skill, ["fixture:upper-if-skilled"], 3, _executor, is_cancelled=cancelled)
    assert report.cancelled
    assert len(report.rows) == 1
    assert report.summary["comparison"]["graded_models"] == 0
    assert report.summary["comparison"]["solved_with"] == 0
    assert report.summary["per_model"][0]["outcome"] == "partial"
    assert report.summary["per_model"][0]["reason"] == "partial: completed 1/3 planned trial pairs"


def test_ungraded_row_explains_unsupported_container_verifier() -> None:
    skill = load_skill(ROOT / "uppercase-skill")
    task = ArenaTask(ROOT, "container-task", "hello", None, None, "skillsbench")
    row = run_bench(task, skill, ["fixture:echo"], 1, _executor).rows[0]
    assert row.status == "ungraded"
    assert row.without_skill is None and row.with_skill is None and row.uplift is None
    assert row.reason == "ungraded: this task ships a container verifier the light runner does not execute — use a native task"


def test_partial_row_preserves_structured_provider_reason() -> None:
    task = load_task(ROOT / "uppercase-task")
    skill = load_skill(ROOT / "uppercase-skill")
    error = {"code": "provider.key_missing", "kind": "unavailable", "message": "key missing", "context": {"provider": "openai"}}

    def unavailable(tier: str, system: str, user: str) -> ProviderResult:
        return ProviderResult("unavailable", error=error)

    row = run_bench(task, skill, ["openai:gpt-5.6-sol"], 1, unavailable).rows[0]
    assert row.status == "partial"
    assert row.reason == error
