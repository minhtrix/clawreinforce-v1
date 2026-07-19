from pathlib import Path

from clawreinforce.core.certify import certify_skill
from clawreinforce.core.models import ProviderResult
from clawreinforce.core.skill import load_skill


EXAMPLE = Path(__file__).parents[1] / "examples" / "hello-skill"


def test_certification_reports_coverage() -> None:
    skill = load_skill(EXAMPLE)
    report = certify_skill(skill, ["fixture:echo"], 2, lambda tier, system, user: ProviderResult("completed", output=user))
    tier = report.tiers[0]
    assert tier.pass_rate == 1.0
    assert tier.coverage == {"completed": 4, "expected": 4, "passed": 4}


def test_unavailable_is_not_zero_percent() -> None:
    skill = load_skill(EXAMPLE)
    missing = ProviderResult("unavailable", error={"code": "provider.key_missing"})
    report = certify_skill(skill, ["openai:gpt-5.6-sol"], 1, lambda *_: missing)
    assert report.tiers[0].pass_rate is None
    assert report.tiers[0].status == "unavailable"

