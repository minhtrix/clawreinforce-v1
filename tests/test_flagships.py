from pathlib import Path

import pytest

from clawreinforce.adapters.providers import ProviderHub
from clawreinforce.core.arena import load_task, run_bench, task_health
from clawreinforce.core.certify import certify_skill
from clawreinforce.core.skill import load_skill, parse_frontmatter


ROOT = Path(__file__).parents[1]
SCENARIOS = (
    ("incident-triage-skill", "incident-triage-task", "operations", "medium"),
    ("privacy-redaction-skill", "privacy-redaction-task", "security", "medium"),
    ("api-migration-skill", "api-migration-task", "coding", "hard"),
)


@pytest.mark.parametrize("skill_name,task_name,category,difficulty", SCENARIOS)
def test_flagship_has_frozen_cases_and_reference_coverage(
    skill_name: str, task_name: str, category: str, difficulty: str
) -> None:
    skill = load_skill(ROOT / "examples" / skill_name)
    metadata, _ = parse_frontmatter(skill.file.read_text(encoding="utf-8"))
    assert metadata["kind"] == "flagship"
    assert metadata["category"] == category
    assert metadata["difficulty"] == difficulty
    assert len(skill.cases) == 10
    assert len({case.id for case in skill.cases}) == 10

    report = certify_skill(skill, ["fixture:reference"], 1, ProviderHub(ROOT).execute)
    assert report.tiers[0].coverage == {"completed": 10, "expected": 10, "passed": 10}
    assert report.tiers[0].pass_rate == 1.0

    task = load_task(ROOT / "examples" / task_name)
    assert task.category == category
    assert task.difficulty == difficulty
    assert task_health(task)["healthy"] is True


@pytest.mark.parametrize("skill_name,task_name,category,difficulty", SCENARIOS)
def test_flagship_reference_arena_proves_controlled_uplift(
    skill_name: str, task_name: str, category: str, difficulty: str
) -> None:
    skill = load_skill(ROOT / "examples" / skill_name)
    task = load_task(ROOT / "examples" / task_name)
    report = run_bench(task, skill, ["fixture:reference"], 2, ProviderHub(ROOT).execute)
    assert report.summary["coverage"] == {"completed_rows": 2, "expected_rows": 2}
    assert report.summary["without_skill"] == 0.0
    assert report.summary["with_skill"] == 1.0
    assert report.summary["uplift"] == 1.0
