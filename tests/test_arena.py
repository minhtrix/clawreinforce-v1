from pathlib import Path

from clawreinforce.core.arena import load_task, run_bench, task_health
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

