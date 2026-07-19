from __future__ import annotations

import shutil
import tempfile
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from clawreinforce.core.fetch import fetch_github_tree
from clawreinforce.errors import ClawError


SKILLSBENCH_REPO = "https://github.com/benchflow-ai/skillsbench/tree/main/tasks"


def normalize_task_source(source: str) -> str:
    parsed = urllib.parse.urlparse(source)
    if parsed.netloc.lower() in {"skillsbench.ai", "www.skillsbench.ai"}:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) == 2 and parts[0] == "tasks":
            return f"{SKILLSBENCH_REPO}/{parts[1]}"
        raise ClawError("task.skillsbench_url", "validation", "SkillsBench URL must look like /tasks/slug")
    return source


@contextmanager
def fetched_task(source: str) -> Iterator[Path]:
    normalized = normalize_task_source(source)
    with tempfile.TemporaryDirectory(prefix="clawreinforce-task-") as raw:
        local = Path(normalized)
        slug = local.name if local.exists() else Path(urllib.parse.urlparse(normalized).path).name
        target = Path(raw) / (slug or "task")
        if local.exists():
            selected = local if local.is_dir() else local.parent
            shutil.copytree(selected, target)
        elif normalized.startswith("https://github.com/"):
            fetch_github_tree(normalized, target)
        else:
            raise ClawError("task.source", "validation", "task source must be a local path, GitHub URL, or SkillsBench URL")
        yield target
