import json
import sys

from clawreinforce.core.checks import run_check
from clawreinforce.core.models import CheckSpec


def test_text_checks() -> None:
    assert run_check(CheckSpec("equals", "hello"), "hello\n").passed
    assert run_check(CheckSpec("contains", "ell"), "hello").passed
    assert run_check(CheckSpec("not_contains", "secret"), "safe").passed
    assert run_check(CheckSpec("regex", r"h.llo"), "hello").passed


def test_exec_runs_candidate_in_temp_directory() -> None:
    spec = CheckSpec("exec", options={"command": [sys.executable, "candidate.py"]})
    assert run_check(spec, "print('isolated')").passed
    assert not run_check(spec, "raise SystemExit(3)").passed


def test_task_author_grader_overrides_emitted_files() -> None:
    grader = "from pathlib import Path\nassert Path('answer.txt').read_text() == '42'\n"
    output = json.dumps({"answer.txt": "42", "__grader__.py": "raise SystemExit(9)"})
    result = run_check(CheckSpec("task", options={"grader": grader}), output)
    assert result.passed


def test_agent_check_is_explicitly_single_shot() -> None:
    grader = "from pathlib import Path\nassert Path('answer.txt').read_text() == '42'\n"
    result = run_check(CheckSpec("agent", options={"grader": grader}), json.dumps({"answer.txt": "42"}))
    assert result.passed
    assert "single-shot (no tool loop yet)" in result.message


def test_dry_run_never_executes_code() -> None:
    result = run_check(CheckSpec("exec"), "raise RuntimeError('must not run')", dry_run=True)
    assert not result.passed
    assert "not executed" in result.message
