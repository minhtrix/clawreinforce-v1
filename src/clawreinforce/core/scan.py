from __future__ import annotations

import re

from clawreinforce.core.models import Finding, Skill


DANGEROUS = {
    "curl_pipe_shell": r"curl\b.{0,120}\|\s*(?:sh|bash|zsh)\b",
    "recursive_delete": r"(?:rm\s+-rf|Remove-Item\s+.*-Recurse)",
    "secret_access": r"(?:[/\\]\.ssh\b|[/\\]\.aws\b|(?:cat|type|Get-Content)\s+[^\n]*\.env\b)"
}
BROAD_SCOPE = ("always", "everything", "all files", "entire system", "never ask")


def scan_skill(skill: Skill, max_lines: int = 300) -> list[Finding]:
    findings: list[Finding] = []
    lines = skill.file.read_text(encoding="utf-8").splitlines()
    if not skill.description:
        findings.append(Finding("metadata.description", "medium", "description is missing", "SKILL.md:1"))
    if len(lines) > max_lines:
        findings.append(
            Finding("bloat.lines", "medium", f"SKILL.md has {len(lines)} lines; limit is {max_lines}", "SKILL.md")
        )
    lower = skill.body.lower()
    broad = [phrase for phrase in BROAD_SCOPE if phrase in lower]
    if broad:
        findings.append(
            Finding("scope.broad", "medium", f"broad instructions: {', '.join(broad)}", "SKILL.md")
        )
    for code, pattern in DANGEROUS.items():
        match = re.search(pattern, skill.body, flags=re.IGNORECASE | re.DOTALL)
        if match:
            line = skill.body[: match.start()].count("\n") + 1
            findings.append(Finding(f"security.{code}", "high", "dangerous instruction pattern", f"SKILL.md:{line}"))
    for path in skill.root.rglob("*"):
        if path.is_symlink():
            findings.append(
                Finding("security.symlink", "high", "symlinked skill content is not trusted", str(path.relative_to(skill.root)))
            )
    return findings
