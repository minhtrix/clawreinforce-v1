import io
import json
import urllib.error
from pathlib import Path
from typing import Any

from clawreinforce.adapters.providers import ProviderHub


class RecordingHub(ProviderHub):
    def __init__(self, project_root: Path) -> None:
        super().__init__(project_root)
        self.request: tuple[str, str, Any, dict[str, str]] | None = None

    def _request(self, method: str, url: str, payload: Any, headers: dict[str, str]) -> dict[str, Any]:
        self.request = (method, url, payload, headers)
        if method == "GET":
            return {"models": [{"name": "model-b"}, {"model": "model-a"}]}
        return {"message": {"content": "ok"}, "prompt_eval_count": 2, "eval_count": 1}


class CompatibleHub(ProviderHub):
    def __init__(self, project_root: Path, *, require_completion_key: bool = False) -> None:
        super().__init__(project_root)
        self.require_completion_key = require_completion_key
        self.payloads: list[dict[str, Any]] = []

    def _request(self, method: str, url: str, payload: Any, headers: dict[str, str]) -> dict[str, Any]:
        assert method == "POST"
        self.payloads.append(dict(payload))
        if self.require_completion_key and len(self.payloads) == 1:
            body = io.BytesIO(b'{"error":"use max_completion_tokens for this model"}')
            raise urllib.error.HTTPError(url, 400, "Bad Request", {}, body)
        return {
            "choices": [{"message": {"content": "compatible-ok"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1},
        }


class OpenAIHub(ProviderHub):
    def __init__(self, project_root: Path) -> None:
        super().__init__(project_root)
        self.request: tuple[str, str, Any, dict[str, str]] | None = None

    def _request(self, method: str, url: str, payload: Any, headers: dict[str, str]) -> dict[str, Any]:
        self.request = (method, url, payload, headers)
        return {"output_text": "OPENAI_OK", "usage": {"input_tokens": 4, "output_tokens": 1}}


def _config(root: Path) -> None:
    store = root / ".clawreinforce"
    store.mkdir()
    (store / "providers.json").write_text(
        json.dumps({"ollama": {"enabled": False}, "ollama-cloud": {"api_key": "test-key"}}), encoding="utf-8"
    )


def _compatible_config(root: Path) -> None:
    store = root / ".clawreinforce"
    store.mkdir()
    (store / "providers.json").write_text(
        json.dumps({"deepseek": {"base_url": "https://compatible.invalid/v1", "api_key": "test-key"}}),
        encoding="utf-8",
    )


def test_ollama_cloud_discovers_models_with_bearer_auth(tmp_path: Path) -> None:
    _config(tmp_path)
    hub = RecordingHub(tmp_path)
    result = hub.discover("ollama-cloud")
    assert json.loads(result.output or "[]") == ["model-a", "model-b"]
    assert hub.request is not None
    assert hub.request[1] == "https://ollama.com/api/tags"
    assert hub.request[3]["Authorization"] == "Bearer test-key"
    assert "ollama" not in {row["provider"] for row in hub.status()}


def test_ollama_cloud_chat_uses_cloud_endpoint(tmp_path: Path) -> None:
    _config(tmp_path)
    hub = RecordingHub(tmp_path)
    result = hub.execute("ollama-cloud:model-a", "system", "user")
    assert result.output == "ok"
    assert hub.request is not None
    assert hub.request[1] == "https://ollama.com/api/chat"


def test_compatible_provider_sends_max_tokens_first(tmp_path: Path) -> None:
    _compatible_config(tmp_path)
    hub = CompatibleHub(tmp_path)
    result = hub.execute("deepseek:model-a", "system", "user")
    assert result.output == "compatible-ok"
    assert len(hub.payloads) == 1
    assert hub.payloads[0]["max_tokens"] == 4096
    assert "max_completion_tokens" not in hub.payloads[0]


def test_compatible_provider_retries_once_with_completion_key(tmp_path: Path) -> None:
    _compatible_config(tmp_path)
    hub = CompatibleHub(tmp_path, require_completion_key=True)
    result = hub.execute("deepseek:model-a", "system", "user")
    assert result.output == "compatible-ok"
    assert len(hub.payloads) == 2
    assert "max_tokens" in hub.payloads[0]
    assert "max_tokens" not in hub.payloads[1]
    assert hub.payloads[1]["max_completion_tokens"] == 4096


def test_default_registry_exposes_ready_and_key_missing_states(tmp_path: Path, monkeypatch) -> None:
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OLLAMA_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    rows = {row["provider"]: row for row in ProviderHub(tmp_path).status()}
    assert set(rows) == {"openai", "anthropic", "ollama", "ollama-cloud", "fixture"}
    assert rows["openai"]["key_source"] == "none"
    assert rows["openai"]["state"] == "key_missing"
    assert rows["anthropic"]["state"] == "key_missing"
    assert rows["ollama"]["state"] == "ready"


def test_default_openai_tier_uses_responses_api_when_key_is_set(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    store = tmp_path / ".clawreinforce"
    store.mkdir()
    (store / "providers.json").write_text(json.dumps({"openai": {"api_key": "test-key"}}), encoding="utf-8")
    hub = OpenAIHub(tmp_path)
    result = hub.execute("openai:gpt-5.6-sol", "system", "user")
    assert result.output == "OPENAI_OK"
    assert hub.request is not None
    assert hub.request[1] == "https://api.openai.com/v1/responses"
    assert hub.request[2]["model"] == "gpt-5.6-sol"
    assert hub.request[2]["reasoning"] == {"effort": "low"}
    assert hub.request[2]["text"] == {"verbosity": "low"}
    assert hub.request[3]["Authorization"] == "Bearer test-key"


def test_openai_gpt4_omits_gpt5_only_controls(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    store = tmp_path / ".clawreinforce"
    store.mkdir()
    (store / "providers.json").write_text(json.dumps({"openai": {"api_key": "test-key"}}), encoding="utf-8")
    hub = OpenAIHub(tmp_path)
    result = hub.execute("openai:gpt-4.1", "system", "user")
    assert result.output == "OPENAI_OK"
    assert hub.request is not None
    assert hub.request[1] == "https://api.openai.com/v1/responses"
    assert hub.request[2]["model"] == "gpt-4.1"
    assert "reasoning" not in hub.request[2]
    assert "text" not in hub.request[2]
