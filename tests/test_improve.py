from clawreinforce.core.improve import gate_rewrite, uplift_gate, verified_examples
from clawreinforce.core.models import CheckSpec, GoldenCase


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

