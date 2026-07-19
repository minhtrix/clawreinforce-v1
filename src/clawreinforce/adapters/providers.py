from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from clawreinforce.core.models import ProviderResult


DEFAULTS: dict[str, dict[str, Any]] = {
    "openai": {"kind": "openai", "base_url": "https://api.openai.com/v1", "env": "OPENAI_API_KEY", "requires_key": True},
    "anthropic": {"kind": "anthropic", "base_url": "https://api.anthropic.com/v1", "env": "ANTHROPIC_API_KEY", "requires_key": True},
    "ollama": {"kind": "ollama", "base_url": "http://127.0.0.1:11434", "env": None, "requires_key": False},
    "ollama-cloud": {"kind": "ollama", "base_url": "https://ollama.com", "env": "OLLAMA_API_KEY", "requires_key": True},
}


class ProviderHub:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.config = self._load_file()

    def _load_file(self) -> dict[str, Any]:
        path = self.project_root / ".clawreinforce" / "providers.json"
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _settings(self, provider: str) -> dict[str, Any]:
        values = {**DEFAULTS.get(provider, {}), **dict(self.config.get(provider, {}))}
        env_name = values.get("env")
        env_key = os.environ.get(str(env_name)) if env_name else None
        values["api_key"] = env_key or values.get("api_key")
        values["key_source"] = "env" if env_key else ("file" if values.get("api_key") else "none")
        return values

    def status(self) -> list[dict[str, Any]]:
        names = sorted(set(DEFAULTS) | set(self.config))
        rows = []
        for name in names:
            settings = self._settings(name)
            if not settings.get("enabled", True):
                continue
            rows.append(
                {
                    "provider": name,
                    "base_url": settings.get("base_url"),
                    "key_source": settings["key_source"],
                    "configured": bool(settings.get("api_key")) or not settings.get("requires_key", False),
                    "last_error": None,
                }
            )
        rows.append(
            {"provider": "fixture", "base_url": None, "key_source": "built_in", "configured": True, "last_error": None}
        )
        return rows

    def execute(self, tier: str, system: str, user: str) -> ProviderResult:
        if ":" not in tier:
            return _error("tier.invalid", "validation", "tier must be provider:model", tier=tier)
        provider, model = tier.split(":", 1)
        if provider == "fixture" and model == "echo":
            return ProviderResult("completed", output=user)
        if provider == "fixture" and model == "upper-if-skilled":
            return ProviderResult("completed", output=user.upper() if "<skill>" in system else user)
        settings = self._settings(provider)
        kind = str(settings.get("kind", provider))
        if not settings.get("enabled", True):
            return _error("provider.disabled", "unavailable", f"{provider} is disabled", provider=provider)
        if settings.get("requires_key") and not settings.get("api_key"):
            return _error("provider.key_missing", "unavailable", f"{provider} API key is missing", provider=provider)
        try:
            if kind == "openai":
                return self._openai(model, system, user, settings)
            if kind == "anthropic":
                return self._anthropic(model, system, user, settings)
            if kind == "ollama":
                return self._ollama(model, system, user, settings)
            if provider in self.config:
                return self._compatible(model, system, user, settings)
            return _error("provider.unknown", "validation", f"unknown provider: {provider}")
        except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, TypeError) as exc:
            return _error("provider.request_failed", "unavailable", str(exc), provider=provider, model=model)

    def discover(self, provider: str) -> ProviderResult:
        settings = self._settings(provider)
        kind = str(settings.get("kind", provider))
        if not settings.get("enabled", True):
            return _error("provider.disabled", "unavailable", "provider is disabled", provider=provider)
        if settings.get("requires_key") and not settings.get("api_key"):
            return _error("provider.key_missing", "unavailable", "API key is missing", provider=provider)
        try:
            url = str(settings.get("base_url", "")).rstrip("/")
            if kind == "ollama":
                payload = self._request("GET", url + "/api/tags", None, self._headers(kind, settings))
                models = [row.get("name") or row.get("model") for row in payload.get("models", [])]
            else:
                headers = self._headers(kind, settings)
                payload = self._request("GET", url + "/models", None, headers)
                models = [row["id"] for row in payload.get("data", [])]
            return ProviderResult("completed", output=json.dumps(sorted(model for model in models if model)))
        except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, TypeError) as exc:
            return _error("provider.discovery_failed", "unavailable", str(exc), provider=provider)

    def _headers(self, provider: str, settings: dict[str, Any]) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.get("api_key"):
            if provider == "anthropic":
                headers.update({"x-api-key": settings["api_key"], "anthropic-version": "2023-06-01"})
            else:
                headers["Authorization"] = f"Bearer {settings['api_key']}"
        return headers

    def _request(self, method: str, url: str, payload: Any, headers: dict[str, str]) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))

    def _openai(self, model: str, system: str, user: str, settings: dict[str, Any]) -> ProviderResult:
        payload = {
            "model": model,
            "instructions": system,
            "input": user,
            "reasoning": {"effort": "low"},
            "text": {"verbosity": "low"},
            "max_output_tokens": 4096,
        }
        data = self._request("POST", settings["base_url"].rstrip("/") + "/responses", payload, self._headers("openai", settings))
        output = data.get("output_text") or _responses_text(data.get("output", []))
        usage = data.get("usage", {})
        return ProviderResult("completed", output=output, input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"))

    def _anthropic(self, model: str, system: str, user: str, settings: dict[str, Any]) -> ProviderResult:
        payload = {"model": model, "system": system, "messages": [{"role": "user", "content": user}], "max_tokens": 4096}
        data = self._request("POST", settings["base_url"].rstrip("/") + "/messages", payload, self._headers("anthropic", settings))
        output = "".join(item.get("text", "") for item in data.get("content", []) if item.get("type") == "text")
        usage = data.get("usage", {})
        return ProviderResult("completed", output=output, input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"))

    def _ollama(self, model: str, system: str, user: str, settings: dict[str, Any]) -> ProviderResult:
        payload = {"model": model, "stream": False, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        data = self._request("POST", settings["base_url"].rstrip("/") + "/api/chat", payload, self._headers("ollama", settings))
        return ProviderResult("completed", output=data["message"]["content"], input_tokens=data.get("prompt_eval_count"), output_tokens=data.get("eval_count"))

    def _compatible(self, model: str, system: str, user: str, settings: dict[str, Any]) -> ProviderResult:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": 4096,
        }
        url = settings["base_url"].rstrip("/") + "/chat/completions"
        headers = self._headers("compatible", settings)
        try:
            data = self._request("POST", url, payload, headers)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code != 400 or "max_completion_tokens" not in body.lower():
                raise
            retry_payload = {**payload, "max_completion_tokens": payload["max_tokens"]}
            del retry_payload["max_tokens"]
            data = self._request("POST", url, retry_payload, headers)
        usage = data.get("usage", {})
        return ProviderResult("completed", output=data["choices"][0]["message"]["content"], input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"))


def _responses_text(items: list[dict[str, Any]]) -> str:
    return "".join(
        content.get("text", "")
        for item in items
        if item.get("type") == "message"
        for content in item.get("content", [])
        if content.get("type") == "output_text"
    )


def _error(code: str, kind: str, message: str, **context: Any) -> ProviderResult:
    return ProviderResult("unavailable", error={"code": code, "kind": kind, "message": message, "context": context})
