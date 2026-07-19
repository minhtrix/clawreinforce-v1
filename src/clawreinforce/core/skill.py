from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clawreinforce.core.models import CheckSpec, GoldenCase, Skill
from clawreinforce.errors import ClawError


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip("\"'")
    return meta, text[end + 5 :]


def _load_cases(root: Path) -> tuple[GoldenCase, ...]:
    candidates = (root / "cases.json", root / ".clawreinforce" / "cases.json")
    case_file = next((path for path in candidates if path.is_file()), None)
    if case_file is None:
        return ()
    try:
        raw: Any = json.loads(case_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClawError("cases.invalid", "validation", str(exc), path=str(case_file)) from exc
    if not isinstance(raw, list):
        raise ClawError("cases.shape", "validation", "cases.json must contain a list")
    cases: list[GoldenCase] = []
    for index, item in enumerate(raw):
        try:
            check = item["check"]
            cases.append(
                GoldenCase(
                    id=str(item["id"]),
                    input=str(item["input"]),
                    check=CheckSpec(
                        kind=str(check["kind"]),
                        value=check.get("value"),
                        options=dict(check.get("options", {})),
                    ),
                    fixture_output=item.get("fixture_output"),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ClawError(
                "cases.item_invalid", "validation", str(exc), index=index
            ) from exc
    return tuple(cases)


def load_skill(path: str | Path) -> Skill:
    requested = Path(path).resolve()
    skill_file = requested / "SKILL.md" if requested.is_dir() else requested
    if not skill_file.is_file():
        raise ClawError("skill.missing", "not_found", "SKILL.md was not found", path=str(requested))
    text = skill_file.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    root = skill_file.parent
    return Skill(
        root=root,
        file=skill_file,
        name=meta.get("name", root.name),
        description=meta.get("description", ""),
        body=body.strip(),
        cases=_load_cases(root),
    )
