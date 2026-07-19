import json
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


def _config(root: Path) -> None:
    store = root / ".clawreinforce"
    store.mkdir()
    (store / "providers.json").write_text(
        json.dumps({"ollama": {"enabled": False}, "ollama-cloud": {"api_key": "test-key"}}), encoding="utf-8"
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

