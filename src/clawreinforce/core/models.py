from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CheckSpec:
    kind: str
    value: Any = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GoldenCase:
    id: str
    input: str
    check: CheckSpec
    fixture_output: str | None = None


@dataclass(frozen=True, slots=True)
class Skill:
    root: Path
    file: Path
    name: str
    description: str
    body: str
    cases: tuple[GoldenCase, ...]


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: str
    message: str
    location: str


@dataclass(frozen=True, slots=True)
class CheckResult:
    passed: bool
    kind: str
    message: str
    duration_ms: int = 0


@dataclass(slots=True)
class ProviderResult:
    status: str
    output: str | None = None
    error: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


@dataclass(slots=True)
class SampleResult:
    case_id: str
    sample: int
    status: str
    check: CheckResult | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TierReport:
    tier: str
    status: str
    pass_rate: float | None
    coverage: dict[str, int]
    samples: list[SampleResult]
    last_error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CertificationReport:
    skill: str
    fingerprint: str
    tiers: list[TierReport]
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

