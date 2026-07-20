import json
from pathlib import Path

import pytest

from clawreinforce.adapters.providers import ProviderHub
from clawreinforce.core.improve import gate_rewrite, improve_skill, uplift_gate, verified_examples
from clawreinforce.core.improve_models import improve_skill_models
from clawreinforce.core.models import CheckSpec, GoldenCase
from clawreinforce.core.models import ProviderResult
from clawreinforce.core.skill import load_skill
from clawreinforce.errors import ClawError


def test_rewrite_gate_requires_fix_without_regression() -> None:
    assert gate_rewrite({"old": True, "target": False}, {"old": True, "target": True}, "target").accepted
    rejected = gate_rewrite({"old": True, "target": False}, {"old": False, "target": True}, "target")
    assert not rejected.accepted
    assert rejected.regressions == ("old",)


def test_uplift_gate_strict_mode() -> None:
    accepted = uplift_gate({"a": 0.4, "b": 0.4}, {"a": 0.7, "b": 0.5})
    assert accepted.accepted
    strict = uplift_gate({"a": 0.4, "b": 0.8}, {"a": 0.9, "b": 0.7}, strict=True)
    assert not strict.accepted


def test_fewshot_examples_are_verified_and_idempotent() -> None:
    cases = [GoldenCase("one", "say hello", CheckSpec("equals", "hello"))]
    body, examples = verified_examples("Rules", cases, {"one": "hello"})
    second, _ = verified_examples(body, cases, {"one": "hello"})
    assert examples
    assert body == second
    assert body.count("## Examples (verified)") == 1


def _broken_uppercase_skill(tmp_path: Path, *, regression: bool = False) -> Path:
    skill = tmp_path / "broken-uppercase"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: broken-uppercase\ndescription: fixture\n---\n\nReturn the supplied text unchanged.\n",
        encoding="utf-8",
    )
    cases = [{"id": "target", "input": "hello", "check": {"kind": "equals", "value": "HELLO"}}]
    if regression:
        cases.insert(0, {"id": "old", "input": "hello", "check": {"kind": "equals", "value": "hello"}})
    (skill / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    return skill


@pytest.mark.parametrize("strategy", ["instruct", "fewshot"])
def test_improve_loop_accepts_only_verified_fixture_rewrite(tmp_path: Path, strategy: str) -> None:
    path = _broken_uppercase_skill(tmp_path)
    report = improve_skill(
        load_skill(path),
        "fixture:upper-if-skilled",
        strategy,
        2,
        ProviderHub(tmp_path).execute,
    )
    assert report.status == "completed"
    assert report.before == {"target": False}
    assert report.after == {"target": True}
    assert report.accepted
    assert report.attempts[0].reason == "target turned green and no prior pass regressed"
    assert report.diff.startswith("--- SKILL.md:before")
    assert path.joinpath("SKILL.md").read_text(encoding="utf-8").endswith("Return the supplied text unchanged.\n")
    if strategy == "fewshot":
        assert "## Examples (verified)" in report.candidate_body
        assert report.attempts[0].verified_examples == ("- Input: hello\n  Output: HELLO",)


def test_improve_loop_rejects_rewrite_that_regresses_green_case(tmp_path: Path) -> None:
    path = _broken_uppercase_skill(tmp_path, regression=True)
    report = improve_skill(
        load_skill(path),
        "fixture:upper-if-skilled",
        "instruct",
        1,
        ProviderHub(tmp_path).execute,
    )
    assert report.status == "rejected"
    assert not report.accepted
    assert report.before == report.after == {"old": True, "target": False}
    assert report.attempts[0].regressions == ("old",)
    assert report.diff == ""


def test_improve_loop_keeps_provider_error_structured(tmp_path: Path) -> None:
    path = _broken_uppercase_skill(tmp_path)
    with pytest.raises(ClawError) as caught:
        improve_skill(load_skill(path), "openai:gpt-5.6-sol", "instruct", 1, ProviderHub(tmp_path).execute)
    assert caught.value.detail.to_dict() == {
        "code": "provider.key_missing",
        "kind": "unavailable",
        "message": "openai API key is missing",
        "context": {"provider": "openai"},
    }


def test_fewshot_loop_preserves_rechecked_examples_across_rewrites(tmp_path: Path) -> None:
    path = _broken_uppercase_skill(tmp_path)
    cases = [
        {"id": "first", "input": "hello", "check": {"kind": "equals", "value": "HELLO"}},
        {"id": "second", "input": "world", "check": {"kind": "equals", "value": "WORLD"}},
    ]
    path.joinpath("cases.json").write_text(json.dumps(cases), encoding="utf-8")
    hub = ProviderHub(tmp_path)
    second_proposals = 0

    def executor(tier: str, system: str, user: str) -> ProviderResult:
        nonlocal second_proposals
        if "CLAWREINFORCE_IMPROVE_FEWSHOT" in system and user == "world":
            second_proposals += 1
            if second_proposals == 1:
                return ProviderResult("completed", output="not verified")
        return hub.execute(tier, system, user)

    report = improve_skill(load_skill(path), "fixture:upper-if-skilled", "fewshot", 2, executor)
    assert report.status == "completed"
    assert len(report.attempts) == 2
    assert report.after == {"first": True, "second": True}
    assert report.candidate_body.count("## Examples (verified)") == 1
    assert "Output: HELLO" in report.candidate_body
    assert "Output: WORLD" in report.candidate_body


def test_multi_model_improve_separates_author_from_gate_models(tmp_path: Path) -> None:
    path = _broken_uppercase_skill(tmp_path)
    report = improve_skill_models(
        load_skill(path),
        "fixture:upper-if-skilled",
        ["fixture:upper-if-skilled", "fixture:echo"],
        "instruct",
        2,
        ProviderHub(tmp_path).execute,
    )
    assert report.author_tier == "fixture:upper-if-skilled"
    assert report.gate_tiers == ("fixture:upper-if-skilled", "fixture:echo")
    assert report.status == "partial" and report.accepted
    rows = {row.tier: row for row in report.per_model}
    assert rows["fixture:upper-if-skilled"].before_pass_rate == 0
    assert rows["fixture:upper-if-skilled"].after_pass_rate == 1
    assert rows["fixture:echo"].before_pass_rate == rows["fixture:echo"].after_pass_rate == 0
    assert report.measurement_note.startswith("One completion per model")


def test_multi_model_gate_rejects_cross_model_regression(tmp_path: Path) -> None:
    path = _broken_uppercase_skill(tmp_path)

    def executor(tier: str, system: str, user: str) -> ProviderResult:
        if tier == "author:rewrite":
            return ProviderResult("completed", output="Return the supplied text in uppercase.")
        rewritten = "uppercase" in system.lower()
        if tier == "gate:target":
            return ProviderResult("completed", output=user.upper() if rewritten else user)
        return ProviderResult("completed", output="BROKEN" if rewritten else "HELLO")

    report = improve_skill_models(
        load_skill(path),
        "author:rewrite",
        ["gate:target", "gate:stable"],
        "instruct",
        1,
        executor,
    )
    assert report.status == "rejected" and not report.accepted
    assert report.attempts[0].regressions == ("gate:stable / target",)
    assert report.diff == ""
