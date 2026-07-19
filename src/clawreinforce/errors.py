from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class ErrorDetail:
    code: str
    kind: str
    message: str
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ClawError(Exception):
    def __init__(self, code: str, kind: str, message: str, **context: Any) -> None:
        super().__init__(message)
        self.detail = ErrorDetail(code, kind, message, context)

