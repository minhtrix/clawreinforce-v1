from pathlib import Path

from clawreinforce.core.arena import load_task, task_health
from clawreinforce.core.fetch import clawhub_slug
from clawreinforce.core.task_source import normalize_task_source


def test_clawhub_page_url_becomes_install_slug() -> None:
    assert clawhub_slug("https://clawhub.ai/jaaneek/skills/x-search") == "x-search"


def test_skillsbench_page_url_becomes_github_tree() -> None:
    source = normalize_task_source("https://www.skillsbench.ai/tasks/3d-scan-calc")
    assert source == "https://github.com/benchflow-ai/skillsbench/tree/main/tasks/3d-scan-calc"


def test_skillsbench_task_is_imported_without_fake_score(tmp_path: Path) -> None:
    (tmp_path / "task.md").write_text("# Demo task\n\nProduce an artifact.", encoding="utf-8")
    (tmp_path / "task.toml").write_text('[metadata]\ndifficulty = "hard"\n', encoding="utf-8")
    task = load_task(tmp_path)
    health = task_health(task)
    assert task.name == "Demo task"
    assert task.difficulty == "hard"
    assert health["healthy"] is None
    assert health["gradeable"] is False
