from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from clawreinforce.adapters.providers import ProviderHub
from clawreinforce.adapters.fixtures import FIXTURE_MODELS
from clawreinforce.core.models import ProviderResult
from clawreinforce.errors import ClawError


class ModelCatalog:
    """Session-cached LLM discovery with fixtures kept explicitly separate."""

    def __init__(self, providers: ProviderHub) -> None:
        self.providers = providers
        self.discovered: dict[str, list[str]] = {"fixture": list(FIXTURE_MODELS)}
        self.last_errors: dict[str, dict[str, Any] | None] = {}

    def catalog(self, *, auto_discover: bool = False) -> dict[str, Any]:
        if auto_discover:
            self._discover_configured_remotes()
        providers = self.providers.status()
        models: list[dict[str, str]] = []
        for row in providers:
            provider = str(row["provider"])
            row["models"] = list(self.discovered.get(provider, []))
            row["last_error"] = self.last_errors.get(provider)
            kind = "fixture" if provider == "fixture" else "llm"
            models.extend(
                {"provider": provider, "model": model, "tier": f"{provider}:{model}", "kind": kind}
                for model in row["models"]
            )
        llms = [row for row in models if row["kind"] == "llm"]
        preset = next(
            (row["tier"] for row in llms if row["tier"] == "openai:gpt-5.6-sol"),
            next(
                (row["tier"] for row in llms if row["tier"] == "anthropic:claude-sonnet-5"),
                next((row["tier"] for row in llms if row["provider"] == "ollama-cloud"), llms[0]["tier"] if llms else "fixture:reference"),
            ),
        )
        return {
            "providers": providers,
            "models": models,
            "preset": preset,
            "llm_count": len(llms),
            "fixture_count": len(models) - len(llms),
        }

    def discover(self, provider: str) -> dict[str, Any]:
        if provider not in {row["provider"] for row in self.providers.status()}:
            raise ClawError("provider.unknown", "validation", f"unknown provider: {provider}", provider=provider)
        result = self.providers.discover(provider)
        self._remember(provider, result)
        return {
            "discovery": {"provider": provider, "status": result.status, "error": result.error},
            **self.catalog(),
        }

    def _discover_configured_remotes(self) -> None:
        names = [
            str(row["provider"])
            for row in self.providers.status()
            if row["provider"] != "fixture"
            and row["configured"]
            and row["key_source"] != "none"
        ]
        if not names:
            return
        with ThreadPoolExecutor(max_workers=min(4, len(names)), thread_name_prefix="model-discovery") as pool:
            results = list(pool.map(self.providers.discover, names))
        for provider, result in zip(names, results, strict=True):
            self._remember(provider, result)

    def _remember(self, provider: str, result: ProviderResult) -> None:
        if result.status == "completed" and result.output:
            values = json.loads(result.output)
            self.discovered[provider] = [str(value) for value in values]
        self.last_errors[provider] = result.error
