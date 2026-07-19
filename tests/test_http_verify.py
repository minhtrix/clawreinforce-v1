import json
import shutil
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path

from clawreinforce.adapters.http import AppState, make_handler


ROOT = Path(__file__).parents[1]


@contextmanager
def api_server(tmp_path: Path):
    shutil.copytree(ROOT / "examples", tmp_path / "examples")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(AppState(tmp_path, ROOT / "web")))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(base: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    method = "GET" if payload is None else "POST"
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read())


def test_verify_http_flow_uses_fixture_without_keys(tmp_path: Path) -> None:
    with api_server(tmp_path) as base:
        catalog = request(base, "/api/skills")
        assert {row["source"] for row in catalog["skills"]} == {
            "examples/hello-skill",
            "examples/uppercase-skill",
        }

        scan = request(base, "/api/scan", {"path": "examples/uppercase-skill"})
        assert scan == {"skill": "uppercase-skill", "findings": []}

        result = request(
            base,
            "/api/certify",
            {"source": "examples/uppercase-skill", "tiers": ["fixture:upper-if-skilled"], "samples": 1},
        )
        tier = result["report"]["tiers"][0]
        assert tier["coverage"] == {"completed": 1, "expected": 1, "passed": 1}
        assert tier["pass_rate"] == 1.0
        assert result["badge_svg"].startswith("<svg")

        checked = request(
            base,
            "/api/certificates/verify",
            {"certificate": result["certificate"], "fingerprint": result["report"]["fingerprint"]},
        )
        assert checked == {"valid": True, "message": "valid"}

        guard = request(
            base,
            "/api/guard",
            {"source": "examples/uppercase-skill", "tiers": ["fixture:upper-if-skilled"], "samples": 1},
        )
        assert guard["verdict"] == "install"
        assert guard["reasons"] == []


def test_verify_http_errors_are_structured(tmp_path: Path) -> None:
    with api_server(tmp_path) as base:
        try:
            request(base, "/api/certify", {"source": "", "tiers": ["fixture:echo"]})
        except urllib.error.HTTPError as exc:
            error = json.loads(exc.read())["error"]
        else:
            raise AssertionError("request should fail")
        assert error == {
            "code": "source.missing",
            "kind": "validation",
            "message": "choose or enter a skill source",
            "context": {},
        }


def test_improve_http_status_is_honest_about_missing_orchestrator(tmp_path: Path) -> None:
    with api_server(tmp_path) as base:
        status = request(base, "/api/improve/status")
    assert status["status"] == "gates_ready"
    assert [gate["id"] for gate in status["gates"]] == ["rewrite", "uplift"]
    assert status["orchestrator"] == {"available": False, "message": "Loop lands next release"}
