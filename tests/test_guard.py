from pathlib import Path

from clawreinforce.core.guard import guard_skill
from clawreinforce.core.models import ProviderResult
from clawreinforce.core.skill import load_skill


EXAMPLE = Path(__file__).parents[1] / "examples" / "hello-skill"


def test_guard_installs_clean_certified_skill() -> None:
    skill = load_skill(EXAMPLE)
    result = guard_skill(skill, ["fixture:echo"], 1, lambda tier, system, user: ProviderResult("completed", output=user))
    assert result["verdict"] == "install"


def test_guard_reviews_missing_provider() -> None:
    skill = load_skill(EXAMPLE)
    missing = ProviderResult("unavailable", error={"code": "provider.key_missing"})
    result = guard_skill(skill, ["openai:gpt-5.6-sol"], 1, lambda *_: missing)
    assert result["verdict"] == "review"

