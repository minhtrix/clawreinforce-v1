import json
from pathlib import Path
from typing import Any

from clawreinforce.adapters.provider_probe import local_status, probe_model
from clawreinforce.adapters.providers import ProviderHub
from clawreinforce.core.models import ProviderResult


class ProbeHub(ProviderHub):
    def __init__(self, root: Path, result: ProviderResult) -> None:
        super().__init__(root)
        self.result = result
        self.call: tuple[str, str, str, int] | None = None

    def execute(self, tier: str, system: str, user: str, max_tokens: int = 4096) -> ProviderResult:
        self.call = (tier, system, user, max_tokens)
        return self.result


def test_probe_is_small_and_reports_real_latency(tmp_path: Path) -> None:
    hub = ProbeHub(tmp_path, ProviderResult("completed", output="OK", input_tokens=5, output_tokens=1))
    ticks = iter((10.0, 10.042))
    result = probe_model(hub, "ollama-cloud:gpt-oss:120b", lambda: next(ticks))
    assert result == {
        "ok": True,
        "model": "ollama-cloud:gpt-oss:120b",
        "latency_ms": 42,
        "input_tokens": 5,
        "output_tokens": 1,
    }
    assert hub.call is not None and hub.call[0] == "ollama-cloud:gpt-oss:120b"
    assert hub.call[3] == 16


def test_probe_preserves_structured_provider_error(tmp_path: Path) -> None:
    error = {"code": "provider.key_missing", "kind": "unavailable", "message": "key missing", "context": {}}
    hub = ProbeHub(tmp_path, ProviderResult("unavailable", error=error))
    ticks = iter((1.0, 1.001))
    result = probe_model(hub, "openai:gpt-5.6-sol", lambda: next(ticks))
    assert result["ok"] is False
    assert result["error"] == error


def test_probe_rejects_invalid_tier_without_calling_provider(tmp_path: Path) -> None:
    hub = ProbeHub(tmp_path, ProviderResult("completed", output="OK"))
    result = probe_model(hub, "only-a-provider")
    assert result["error"]["code"] == "tier.invalid"
    assert hub.call is None


def test_local_status_reports_ollama_vram_and_installed_models(tmp_path: Path) -> None:
    def get_json(url: str, headers: dict[str, str] | None, timeout: float) -> dict[str, Any]:
        if url.endswith("/api/ps"):
            return {"models": [{"name": "llama3.1:8b", "size_vram": 6 * 1024**3}]}
        return {"models": [{"name": "mistral"}, {"model": "llama3.1:8b"}]}

    status = local_status(ProviderHub(tmp_path), get_json)
    assert status["ollama"]["reachable"] is True
    assert status["ollama"]["running"] == [{"name": "llama3.1:8b", "vram_bytes": 6 * 1024**3}]
    assert status["ollama"]["models"] == ["llama3.1:8b", "mistral"]


def test_local_status_lists_keyless_compatible_endpoints(tmp_path: Path) -> None:
    store = tmp_path / ".clawreinforce"
    store.mkdir()
    (store / "providers.json").write_text(
        json.dumps(
            {
                "vllm": {
                    "base_url": "http://127.0.0.1:8000/v1",
                    "requires_key": False,
                    "default_model": "qwen2.5",
                    "models": ["qwen2.5"],
                }
            }
        ),
        encoding="utf-8",
    )

    def get_json(url: str, headers: dict[str, str] | None, timeout: float) -> dict[str, Any]:
        assert url == "http://127.0.0.1:8000/v1/models"
        return {"data": [{"id": "qwen2.5"}, {"id": "qwen3"}]}

    status = local_status(ProviderHub(tmp_path), get_json)
    assert status["custom"] == [
        {
            "name": "vllm",
            "base_url": "http://127.0.0.1:8000/v1",
            "default_model": "qwen2.5",
            "models": ["qwen2.5", "qwen3"],
            "reachable": True,
            "error": None,
        }
    ]


def test_local_status_is_honest_when_every_ollama_call_fails(tmp_path: Path) -> None:
    def get_json(url: str, headers: dict[str, str] | None, timeout: float) -> dict[str, Any]:
        raise OSError("connection refused")

    status = local_status(ProviderHub(tmp_path), get_json)
    assert status["ollama"]["reachable"] is False
    assert status["ollama"]["running"] == []
    assert status["ollama"]["error"]["code"] == "provider.local_unreachable"
