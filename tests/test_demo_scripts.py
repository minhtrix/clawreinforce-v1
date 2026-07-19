from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_demo_scripts_cover_the_same_executable_story() -> None:
    for relative in ("demo/demo.ps1", "demo/demo.sh"):
        script = (ROOT / relative).read_text(encoding="utf-8")
        assert "https://clawhub.ai/jaaneek/skills/x-search" in script
        assert "fixture:upper-if-skilled" in script
        assert "uppercase-certificate.json" in script
        assert "arena.csv" in script and "arena.png" in script
        assert "clawreinforce serve" in script


def test_demo_docs_keep_api_cost_claim_honest() -> None:
    docs = (ROOT / "docs/DEMO.md").read_text(encoding="utf-8")
    assert "short-circuits before provider execution" in docs
    assert "This probe is the only key-requiring command" in docs
    assert "under $0.01" in docs
