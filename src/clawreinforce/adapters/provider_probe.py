from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Callable

from clawreinforce.adapters.providers import DEFAULTS, ProviderHub


JsonGetter = Callable[[str, dict[str, str] | None, float], dict[str, Any]]


def _detail(code: str, message: str, **context: Any) -> dict[str, Any]:
    return {"code": code, "kind": "unavailable", "message": message, "context": context}


def probe_model(hub: ProviderHub, tier: str, clock: Callable[[], float] = time.perf_counter) -> dict[str, Any]:
    provider, separator, model = str(tier).partition(":")
    if not provider or not separator or not model:
        return {
            "ok": False,
            "model": tier,
            "error": _detail("tier.invalid", "tier must be provider:model", tier=tier),
        }
    started = clock()
    result = hub.execute(tier, "You are a connectivity probe. Reply with exactly: OK", "OK", max_tokens=16)
    latency_ms = max(0, round((clock() - started) * 1000))
    if result.status != "completed":
        return {"ok": False, "model": tier, "latency_ms": latency_ms, "error": result.error}
    if not (result.output or "").strip():
        return {
            "ok": False,
            "model": tier,
            "latency_ms": latency_ms,
            "error": _detail("provider.empty_response", "provider returned an empty response", provider=provider, model=model),
        }
    return {
        "ok": True,
        "model": tier,
        "latency_ms": latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }


def _get_json(url: str, headers: dict[str, str] | None = None, timeout: float = 2.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "clawreinforce", **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _models_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    for suffix in ("/chat/completions", "/responses"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base + "/models"


def _ollama_status(hub: ProviderHub, get_json: JsonGetter) -> dict[str, Any]:
    settings = hub._settings("ollama")
    base_url = str(settings.get("base_url", "")).rstrip("/")
    status: dict[str, Any] = {"reachable": False, "running": [], "models": [], "error": None}
    failures: list[str] = []
    try:
        payload = get_json(base_url + "/api/ps", hub._headers("ollama", settings), 2.0)
        status["reachable"] = True
        status["running"] = [
            {"name": row.get("name") or row.get("model") or "", "vram_bytes": row.get("size_vram")}
            for row in payload.get("models", [])
        ]
    except Exception as exc:
        failures.append(f"/api/ps: {exc}")
    try:
        payload = get_json(base_url + "/api/tags", hub._headers("ollama", settings), 2.0)
        status["reachable"] = True
        status["models"] = sorted(
            name for row in payload.get("models", []) if (name := row.get("name") or row.get("model"))
        )
    except Exception as exc:
        failures.append(f"/api/tags: {exc}")
    if not status["reachable"]:
        status["error"] = _detail(
            "provider.local_unreachable", "; ".join(failures), provider="ollama", base_url=base_url
        )
    return status


def _custom_status(hub: ProviderHub, name: str, get_json: JsonGetter) -> dict[str, Any]:
    settings = hub._settings(name)
    base_url = str(settings.get("base_url", ""))
    row: dict[str, Any] = {
        "name": name,
        "base_url": base_url,
        "default_model": settings.get("default_model"),
        "models": list(settings.get("models") or []),
        "reachable": False,
        "error": None,
    }
    try:
        payload = get_json(_models_url(base_url), hub._headers("compatible", settings), 2.0)
        discovered = [item.get("id") for item in payload.get("data", []) if item.get("id")]
        row["models"] = sorted(set(row["models"]) | set(discovered))
        row["reachable"] = True
    except Exception as exc:
        row["error"] = _detail(
            "provider.local_unreachable", str(exc), provider=name, base_url=base_url
        )
    return row


def local_status(hub: ProviderHub, get_json: JsonGetter = _get_json) -> dict[str, Any]:
    custom = []
    for name in sorted(set(hub.config) - set(DEFAULTS)):
        settings = hub._settings(name)
        if settings.get("enabled", True) and not settings.get("requires_key", False) and settings.get("base_url"):
            custom.append(_custom_status(hub, name, get_json))
    return {"ollama": _ollama_status(hub, get_json), "custom": custom}
