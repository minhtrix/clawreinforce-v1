import json
from pathlib import Path

from clawreinforce.adapters.cli import build_parser, main


def test_help_discloses_single_shot_agent_check() -> None:
    assert "agent check is single-shot (no tool loop yet)" in build_parser().format_help()


def _write_broken_skill(root: Path) -> Path:
    skill = root / "broken"
    skill.mkdir()
    skill.joinpath("SKILL.md").write_text(
        "---\nname: broken\ndescription: keep me\n---\n\nReturn the supplied text unchanged.\n",
        encoding="utf-8",
    )
    skill.joinpath("cases.json").write_text(
        json.dumps([{"id": "target", "input": "hello", "check": {"kind": "equals", "value": "HELLO"}}]),
        encoding="utf-8",
    )
    return skill


def test_improve_cli_dry_run_prints_diff_without_writing(tmp_path: Path, capsys) -> None:
    skill = _write_broken_skill(tmp_path)
    before = skill.joinpath("SKILL.md").read_text(encoding="utf-8")
    exit_code = main(
        ["improve", str(skill), "--tier", "fixture:upper-if-skilled", "--strategy", "instruct", "--max-rewrites", "1"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["dry_run"] and not payload["applied"]
    assert payload["diff"].startswith("--- SKILL.md:before")
    assert skill.joinpath("SKILL.md").read_text(encoding="utf-8") == before


def test_improve_cli_apply_writes_only_accepted_body(tmp_path: Path, capsys) -> None:
    skill = _write_broken_skill(tmp_path)
    exit_code = main(
        ["improve", str(skill), "--tier", "fixture:upper-if-skilled", "--strategy", "fewshot", "--max-rewrites", "1", "--apply"]
    )
    payload = json.loads(capsys.readouterr().out)
    document = skill.joinpath("SKILL.md").read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["applied"] and not payload["dry_run"]
    assert document.startswith("---\nname: broken\ndescription: keep me\n---\n")
    assert "## Examples (verified)" in document


def test_models_cli_has_probe_local_and_model_management_parity(tmp_path: Path, capsys, monkeypatch) -> None:
    def local_json(url: str, headers: dict[str, str] | None = None, timeout: float = 2.0) -> dict:
        return {"models": []}

    monkeypatch.setattr("clawreinforce.adapters.provider_probe._get_json", local_json)
    exit_code = main(
        [
            "models",
            "--project",
            str(tmp_path),
            "--add-model",
            "openai:gpt-5.6-sol",
            "--local",
            "--probe",
            "fixture:echo",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["added"]["models"] == ["gpt-5.6-sol"]
    assert payload["local"]["ollama"]["reachable"] is True
    assert payload["probe"]["ok"] is True
