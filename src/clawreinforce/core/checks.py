from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from clawreinforce.core.models import CheckResult, CheckSpec


MAX_OUTPUT_BYTES = 32_768
DEFAULT_TIMEOUT = 5.0


def _result(start: float, passed: bool, kind: str, message: str) -> CheckResult:
    elapsed = int((time.monotonic() - start) * 1000)
    return CheckResult(passed, kind, message[:1000], elapsed)


def _text_check(spec: CheckSpec, output: str, start: float) -> CheckResult:
    expected = str(spec.value if spec.value is not None else "")
    if spec.kind == "equals":
        passed = output.strip() == expected.strip()
    elif spec.kind == "contains":
        passed = expected in output
    elif spec.kind == "not_contains":
        passed = expected not in output
    else:
        try:
            passed = re.search(expected, output, flags=re.MULTILINE) is not None
        except re.error as exc:
            return _result(start, False, spec.kind, f"invalid regex: {exc}")
    return _result(start, passed, spec.kind, "passed" if passed else "output did not satisfy check")


def _property_check(spec: CheckSpec, output: str, start: float) -> CheckResult:
    try:
        value: Any = json.loads(output)
        for part in str(spec.options.get("path", "")).split("."):
            if part:
                value = value[int(part)] if isinstance(value, list) else value[part]
        expected = spec.value
        passed = value == expected
        return _result(start, passed, spec.kind, "passed" if passed else f"property was {value!r}")
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        return _result(start, False, spec.kind, f"property check failed: {exc}")


def _safe_file(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if root.resolve() not in candidate.parents and candidate != root.resolve():
        raise ValueError(f"unsafe path: {relative}")
    return candidate


def _run(command: list[str], cwd: Path, timeout: float) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={"PATH": str(Path(sys.executable).parent)},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"sandbox process failed: {exc}"
    combined = (completed.stdout + completed.stderr).encode("utf-8")[:MAX_OUTPUT_BYTES]
    summary = combined.decode("utf-8", errors="replace")
    return completed.returncode == 0, summary or f"exit {completed.returncode}"


def _exec_check(spec: CheckSpec, output: str, start: float) -> CheckResult:
    timeout = float(spec.options.get("timeout", DEFAULT_TIMEOUT))
    filename = str(spec.options.get("filename", "candidate.py"))
    command = [str(item) for item in spec.options.get("command", [sys.executable, filename])]
    with tempfile.TemporaryDirectory(prefix="clawreinforce-") as raw:
        root = Path(raw)
        try:
            path = _safe_file(root, filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output, encoding="utf-8")
            for relative, content in dict(spec.options.get("support_files", {})).items():
                support = _safe_file(root, relative)
                support.parent.mkdir(parents=True, exist_ok=True)
                support.write_text(str(content), encoding="utf-8")
        except (OSError, ValueError) as exc:
            return _result(start, False, spec.kind, str(exc))
        passed, message = _run(command, root, timeout)
        return _result(start, passed, spec.kind, message)


def _task_check(spec: CheckSpec, output: str, start: float) -> CheckResult:
    try:
        emitted = json.loads(output)
        if not isinstance(emitted, dict):
            raise ValueError("task output must be a JSON object of path -> content")
    except (json.JSONDecodeError, ValueError) as exc:
        return _result(start, False, spec.kind, str(exc))
    grader = spec.options.get("grader")
    if not isinstance(grader, str) or not grader.strip():
        return _result(start, False, spec.kind, "author-hidden grader is missing")
    with tempfile.TemporaryDirectory(prefix="clawreinforce-task-") as raw:
        root = Path(raw)
        try:
            for relative, content in emitted.items():
                path = _safe_file(root, str(relative))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(str(content), encoding="utf-8")
            grader_path = root / "__grader__.py"
            grader_path.write_text(grader, encoding="utf-8")
        except (OSError, ValueError) as exc:
            return _result(start, False, spec.kind, str(exc))
        passed, message = _run(
            [sys.executable, "__grader__.py"], root, float(spec.options.get("timeout", DEFAULT_TIMEOUT))
        )
        return _result(start, passed, spec.kind, message)


def run_check(spec: CheckSpec, output: str, *, dry_run: bool = False) -> CheckResult:
    start = time.monotonic()
    if dry_run:
        return _result(start, False, spec.kind, "dry_run: code was not executed")
    if spec.kind in {"equals", "contains", "not_contains", "regex"}:
        return _text_check(spec, output, start)
    if spec.kind == "property":
        return _property_check(spec, output, start)
    if spec.kind == "exec":
        return _exec_check(spec, output, start)
    if spec.kind in {"task", "agent"}:
        result = _task_check(spec, output, start)
        if spec.kind == "agent":
            return CheckResult(
                result.passed,
                result.kind,
                f"single-shot (no tool loop yet): {result.message}",
                result.duration_ms,
            )
        return result
    return _result(start, False, spec.kind, f"unsupported check kind: {spec.kind}")
