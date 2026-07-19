from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_event(root: Path, ledger: str, event: dict[str, Any]) -> Path:
    store = root / ".clawreinforce"
    store.mkdir(parents=True, exist_ok=True)
    path = store / f"{ledger}.jsonl"
    record = {"recorded_at": datetime.now(timezone.utc).isoformat(), **event}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
    return path


def read_events(root: Path, ledger: str) -> list[dict[str, Any]]:
    path = root / ".clawreinforce" / f"{ledger}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

