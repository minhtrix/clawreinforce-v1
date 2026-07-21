from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_demo_scripts_cover_the_same_executable_story() -> None:
    for relative in ("demo/demo.ps1", "demo/demo.sh"):
        script = (ROOT / relative).read_text(encoding="utf-8")
        assert "https://clawhub.ai/jaaneek/skills/x-search" in script
        assert "fixture:reference" in script
        assert "incident-triage-skill" in script
        assert "incident-triage-certificate.json" in script
        assert "arena.csv" in script and "arena.png" in script
        assert "serve --project . --host 127.0.0.1" in script
        assert "-m" in script and "clawreinforce" in script


def test_demo_docs_keep_api_cost_claim_honest() -> None:
    docs = (ROOT / "docs/DEMO.md").read_text(encoding="utf-8")
    assert "short-circuits before provider execution" in docs
    assert "This probe is the only key-requiring command" in docs
    assert "under $0.01" in docs


def test_submission_pack_contains_required_judge_gates() -> None:
    docs = (ROOT / "docs/SUBMISSION.md").read_text(encoding="utf-8")
    for required in (
        "Repository URL",
        "Public YouTube demo",
        "Codex /feedback Session ID",
        "Developer Tools",
        "How Codex was used",
        "How GPT-5.6 is used",
        "Existing-project disclosure",
        "Judge quick test — zero keys",
        "signed-out browser",
    ):
        assert required in docs
