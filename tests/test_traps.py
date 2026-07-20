import shutil
from pathlib import Path

import pytest

from clawreinforce.adapters.providers import ProviderHub
from clawreinforce.core.fingerprint import skill_fingerprint
from clawreinforce.core.models import ProviderResult
from clawreinforce.core.skill import load_skill
from clawreinforce.core.traps import TRAP_MARKER, discover_traps, freeze_traps
from clawreinforce.errors import ClawError


ROOT = Path(__file__).parents[1]


def _skill(tmp_path: Path) -> Path:
    path = tmp_path / "improvable-uppercase-skill"
    shutil.copytree(ROOT / "examples" / "improvable-uppercase-skill", path)
    return path


def test_fixture_breaker_finds_reproducible_cross_model_failures(tmp_path: Path) -> None:
    path = _skill(tmp_path)
    report = discover_traps(
        load_skill(path),
        "fixture:upper-if-skilled",
        ["fixture:upper-if-skilled", "fixture:echo"],
        3,
        ProviderHub(tmp_path).execute,
    )

    assert report["candidates_checked"] == 3
    assert report["failing_candidates"] == 2
    assert report["model_trap_failures"] == 4
    assert [(row["tier"], row["passed"], row["total"]) for row in report["per_model"]] == [
        ("fixture:upper-if-skilled", 1, 3),
        ("fixture:echo", 1, 3),
    ]
    first = report["candidates"][0]
    assert first["check"] == {"kind": "equals", "value": "HELLO WORLD"}
    assert first["results"][0]["actual"] == "hello world"
    assert first["results"][0]["reason"] == "output did not satisfy check"


def test_freeze_is_reviewed_append_only_and_changes_certified_input(tmp_path: Path) -> None:
    path = _skill(tmp_path)
    report = discover_traps(
        load_skill(path),
        "fixture:upper-if-skilled",
        ["fixture:upper-if-skilled"],
        3,
        ProviderHub(tmp_path).execute,
    )
    selected = [item for item in report["candidates"] if item["tears_now"]]
    before = skill_fingerprint(path)

    frozen = freeze_traps(path, selected, reviewed=True)
    after = skill_fingerprint(path)
    duplicate = freeze_traps(path, selected, reviewed=True)

    assert len(frozen["added"]) == 2
    assert frozen["append_only"]
    assert before != after
    assert len(load_skill(path).cases) == 3
    assert duplicate["added"] == []
    assert {row["reason"] for row in duplicate["skipped"]} == {"duplicate regression"}
    assert len((path / ".clawreinforce" / "regressions.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_freeze_requires_human_review(tmp_path: Path) -> None:
    with pytest.raises(ClawError) as raised:
        freeze_traps(_skill(tmp_path), [{"id": "K1", "tears_now": True}], reviewed=False)
    assert raised.value.detail.code == "traps.review_required"


def test_provider_failure_stays_structured_and_ungraded(tmp_path: Path) -> None:
    path = _skill(tmp_path)
    fixture = ProviderHub(tmp_path)

    def executor(tier: str, system: str, user: str) -> ProviderResult:
        if TRAP_MARKER in system:
            return fixture.execute("fixture:upper-if-skilled", system, user)
        if tier == "broken:model":
            return ProviderResult(
                "unavailable",
                error={"code": "provider.key_missing", "kind": "unavailable", "message": "key missing", "context": {}},
            )
        return fixture.execute(tier, system, user)

    report = discover_traps(
        load_skill(path),
        "fixture:upper-if-skilled",
        ["broken:model"],
        1,
        executor,
    )
    model = report["per_model"][0]
    result = report["candidates"][0]["results"][0]
    assert model["pass_rate"] is None
    assert model["last_error"]["code"] == "provider.key_missing"
    assert result["passed"] is None
    assert result["reason"] == result["error"]


def test_breaker_unsafe_checks_are_rejected_but_safe_candidates_run(tmp_path: Path) -> None:
    def executor(tier: str, system: str, user: str) -> ProviderResult:
        if TRAP_MARKER in system:
            return ProviderResult(
                "completed",
                output=(
                    '[{"input":"x","check":{"kind":"exec","value":"boom"}},'
                    '{"input":"x","check":{"kind":"equals","value":"x"},"rationale":"safe"}]'
                ),
            )
        return ProviderResult("completed", output=user)

    report = discover_traps(load_skill(_skill(tmp_path)), "fixture:breaker", ["fixture:gate"], 2, executor)
    assert report["candidates_checked"] == 1
    assert report["rejected_candidates"] == [{"candidate": "K1", "reason": "check kind is missing or unsafe"}]
    assert report["candidates"][0]["tears_now"] is False
