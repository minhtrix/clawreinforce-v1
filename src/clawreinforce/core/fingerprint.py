from __future__ import annotations

import hashlib
from pathlib import Path


IGNORED_PARTS = {
    ".clawreinforce",
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "graphify-out",
}


def skill_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and (
            path.relative_to(root).as_posix() == ".clawreinforce/regressions.jsonl"
            or not any(part in IGNORED_PARTS for part in path.relative_to(root).parts)
        )
    )
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return f"sha256:{digest.hexdigest()}"
