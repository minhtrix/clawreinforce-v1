from clawreinforce.adapters.cli import build_parser


def test_help_discloses_single_shot_agent_check() -> None:
    assert "agent check is single-shot (no tool loop yet)" in build_parser().format_help()
