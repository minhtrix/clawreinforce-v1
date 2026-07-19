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
