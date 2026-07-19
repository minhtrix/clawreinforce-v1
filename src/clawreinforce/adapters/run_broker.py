from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RunState:
    run_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    cancelled: bool = False
    finished: bool = False
    condition: threading.Condition = field(default_factory=threading.Condition)

    def emit(self, event: dict[str, Any]) -> None:
        with self.condition:
            self.events.append(event)
            if event.get("type") in {"run_completed", "run_cancelled", "run_failed"}:
                self.finished = True
            self.condition.notify_all()


class RunBroker:
    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = threading.Lock()

    def create(self, run_id: str) -> RunState:
        state = RunState(run_id)
        with self._lock:
            self._runs[run_id] = state
        return state

    def get(self, run_id: str) -> RunState | None:
        with self._lock:
            return self._runs.get(run_id)

    def cancel(self, run_id: str) -> bool:
        state = self.get(run_id)
        if state is None:
            return False
        with state.condition:
            state.cancelled = True
            state.condition.notify_all()
        return True

