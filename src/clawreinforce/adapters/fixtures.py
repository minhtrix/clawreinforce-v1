from __future__ import annotations

import json
import re
from typing import Any

from clawreinforce.core.models import ProviderResult


FIXTURE_MODELS = ("echo", "upper-if-skilled", "reference")


def execute_fixture(model: str, system: str, user: str) -> ProviderResult:
    if model == "echo":
        return ProviderResult("completed", output=user)
    if model == "upper-if-skilled":
        return ProviderResult("completed", output=_upper(system, user))
    if model == "reference":
        return ProviderResult("completed", output=_reference(system, user))
    return ProviderResult(
        "unavailable",
        error={
            "code": "fixture.unknown",
            "kind": "validation",
            "message": f"unknown deterministic fixture: {model}",
            "context": {"model": model},
        },
    )


def _reference(system: str, user: str) -> str:
    body = _skill_body(system)
    match = re.search(r"CLAWREINFORCE_SCENARIO:\s*([a-z-]+)", body)
    if not match:
        return user
    try:
        value = json.loads(user)
        if not isinstance(value, dict):
            return user
        scenario = match.group(1)
        if scenario == "incident-triage":
            result: Any = _incident(value)
        elif scenario == "privacy-redaction":
            result = _redact(value)
        elif scenario == "api-migration":
            result = _migrate(value)
        else:
            return user
        return json.dumps(result, ensure_ascii=False, sort_keys=True)
    except (json.JSONDecodeError, TypeError, ValueError):
        return user


def _incident(value: dict[str, Any]) -> dict[str, Any]:
    incident_id = str(value.get("incident_id", "unknown"))
    service = str(value.get("service", "unknown")).lower()
    signal = str(value.get("severity_signal", "")).lower()
    summary = str(value.get("summary", "")).lower()
    impact = float(value.get("customer_impact_pct", 0) or 0)
    repeated = int(value.get("repeated_count", 0) or 0)
    combined = f"{service} {signal} {summary}"
    if any(word in combined for word in ("active_exploit", "outage", "data_loss")) or impact >= 50:
        severity = "P1"
    elif any(word in combined for word in ("degraded", "latency", "5xx", "regression")) or impact > 0:
        severity = "P2"
    else:
        severity = "P3"
    if any(word in combined for word in ("active_exploit", "credential", "malware")):
        owner = "security"
    elif any(word in combined for word in ("auth", "login", "identity")):
        owner = "identity"
    elif any(word in combined for word in ("payment", "billing", "checkout")):
        owner = "payments"
    else:
        owner = "platform"
    if owner == "security":
        action = "isolate affected systems and page security"
    elif bool(value.get("recent_deploy")):
        action = "rollback recent change and page service owner"
    elif severity == "P1":
        action = f"page {owner} and start incident bridge"
    else:
        action = f"investigate with {owner} owner"
    return {
        "incident_id": incident_id,
        "severity": severity,
        "owner": owner,
        "duplicate": repeated >= 2,
        "action": action,
    }


def _redact(value: dict[str, Any]) -> dict[str, Any]:
    text = str(value.get("text", ""))
    allowlist = [str(item) for item in value.get("allowlist", [])]
    protected: dict[str, str] = {}
    for index, literal in enumerate(sorted(allowlist, key=len, reverse=True)):
        token = f"__ALLOW_{index}__"
        text = text.replace(literal, token)
        protected[token] = literal
    patterns = (
        ("API_KEY", r"\bsk-[A-Za-z0-9]{16,}\b"),
        ("EMAIL", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        ("SSN", r"\b\d{3}-\d{2}-\d{4}\b"),
        ("PHONE", r"(?<!\w)(?:\+1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\w)"),
    )
    kinds: list[str] = []
    count = 0
    for kind, pattern in patterns:
        def replace(_: re.Match[str], label: str = kind) -> str:
            nonlocal count
            count += 1
            if label not in kinds:
                kinds.append(label)
            return f"[{label}]"

        text = re.sub(pattern, replace, text)
    for token, literal in protected.items():
        text = text.replace(token, literal)
    return {"redacted_text": text, "redaction_count": count, "types": kinds}


def _migrate(value: dict[str, Any]) -> dict[str, str]:
    files = value.get("files", {})
    if not isinstance(files, dict):
        raise ValueError("files must be an object")
    migrated: dict[str, str] = {}
    for raw_path, raw_content in files.items():
        content = str(raw_content)
        content = content.replace(".chat.completions.create(", ".responses.create(")
        content = content.replace("messages=", "input=")
        content = re.sub(r"\bmessages\s*:", "input:", content)
        content = content.replace(".choices[0].message.content", ".output_text")
        migrated[str(raw_path)] = content
    return migrated


def _skill_body(system: str) -> str:
    match = re.search(r"<skill>\s*(.*?)\s*</skill>", system, flags=re.DOTALL)
    return match.group(1) if match else ""


def _upper(system: str, user: str) -> str:
    if "CLAWREINFORCE_ADVERSARIAL_TRAPS" in system:
        limit_match = re.search(r"at most (\d+)", system)
        limit = int(limit_match.group(1)) if limit_match else 3
        candidates = [
            {
                "input": "hello world",
                "check": {"kind": "equals", "value": "HELLO WORLD"},
                "rationale": "Exercise spaces and lowercase conversion promised by the skill.",
            },
            {
                "input": "MiXeD-123",
                "check": {"kind": "equals", "value": "MIXED-123"},
                "rationale": "Exercise mixed case while preserving punctuation and digits.",
            },
            {
                "input": "",
                "check": {"kind": "equals", "value": ""},
                "rationale": "Exercise the empty-input boundary without inventing an error contract.",
            },
        ]
        return json.dumps(candidates[:limit])
    if "CLAWREINFORCE_IMPROVE_INSTRUCT" in system:
        return "Return the supplied text in uppercase. Return only the converted text."
    if "CLAWREINFORCE_IMPROVE_FEWSHOT" in system:
        return user.upper()
    body = _skill_body(system)
    if "uppercase" in body.lower():
        return user.upper()
    examples = re.findall(r"- Input: (.*?)\n  Output: (.*?)(?=\n- Input:|\Z)", body, flags=re.DOTALL)
    for case_input, output in examples:
        if case_input.strip() == user.strip():
            return output.strip()
    return user
