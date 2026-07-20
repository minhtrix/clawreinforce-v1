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
            "examples/improvable-uppercase-skill",
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


def test_improve_http_runs_dry_run_then_applies_accepted_body(tmp_path: Path) -> None:
    with api_server(tmp_path) as base:
        status = request(base, "/api/improve/status")
        source = "examples/improvable-uppercase-skill"
        skill_file = tmp_path / source / "SKILL.md"
        before = skill_file.read_text(encoding="utf-8")
        dry_run = request(
            base,
            "/api/improve",
            {
                "source": source,
                "tier": "fixture:upper-if-skilled",
                "strategy": "fewshot",
                "max_rewrites": 1,
                "apply": False,
            },
        )
        assert skill_file.read_text(encoding="utf-8") == before
        assert dry_run["metrics"] == {
            "baseline_score": 0.0,
            "best_score": 1.0,
            "gain_pp": 100.0,
            "accepted_iteration": 1,
            "model_count": 1,
            "check_count": 1,
        }
        assert dry_run["output_path"] == "examples/improvable-uppercase-skill/SKILL.md"
        assert dry_run["write_state"] == "dry_run"
        assert dry_run["attempts"][0]["diagnosis"].startswith("target fixed")
        assert dry_run["attempts"][0]["models"][0]["delta_pp"] == 100.0
        assert dry_run["learned_patterns"][0]["outcome"] == "helped"
        applied = request(
            base,
            "/api/improve",
            {
                "source": source,
                "tier": "fixture:upper-if-skilled",
                "strategy": "fewshot",
                "max_rewrites": 1,
                "apply": True,
            },
        )
        history = request(base, "/api/history")
    assert status["status"] == "loop_ready"
    assert status["orchestrator"] == {"available": True, "message": "Golden rewrite loop available"}
    assert dry_run["status"] == "completed" and dry_run["accepted"]
    assert dry_run["diff"].startswith("--- SKILL.md:before")
    assert dry_run["attempts"][0]["reason"] == "target turned green and no prior pass regressed"
    assert applied["applied"]
    assert applied["write_state"] == "applied"
    assert len(applied["history"]) == 2
    assert len(history["improve_runs"]) == 2
    assert "## Examples (verified)" in skill_file.read_text(encoding="utf-8")


def test_improve_http_accepts_author_and_multiple_gate_models(tmp_path: Path) -> None:
    with api_server(tmp_path) as base:
        result = request(
            base,
            "/api/improve",
            {
                "source": "examples/improvable-uppercase-skill",
                "author_tier": "fixture:upper-if-skilled",
                "gate_tiers": ["fixture:upper-if-skilled", "fixture:echo"],
                "strategy": "instruct",
                "max_rewrites": 2,
                "apply": False,
            },
        )
    assert result["author_tier"] == "fixture:upper-if-skilled"
    assert result["gate_tiers"] == ["fixture:upper-if-skilled", "fixture:echo"]
    assert result["status"] == "partial" and result["accepted"]
    assert [row["tier"] for row in result["per_model"]] == [
        "fixture:upper-if-skilled",
        "fixture:echo",
    ]


def test_traps_http_measures_then_freezes_only_reviewed_selection(tmp_path: Path) -> None:
    with api_server(tmp_path) as base:
        report = request(
            base,
            "/api/traps",
            {
                "source": "examples/improvable-uppercase-skill",
                "breaker_tier": "fixture:upper-if-skilled",
                "gate_tiers": ["fixture:upper-if-skilled", "fixture:echo"],
                "max_traps": 3,
            },
        )
        selected = [item for item in report["candidates"] if item["tears_now"]]
        frozen = request(
            base,
            "/api/traps/freeze",
            {
                "source": "examples/improvable-uppercase-skill",
                "candidates": selected,
                "reviewed": True,
            },
        )
        certified = request(
            base,
            "/api/certify",
            {
                "source": "examples/improvable-uppercase-skill",
                "tiers": ["fixture:upper-if-skilled"],
                "samples": 1,
            },
        )

    assert report["freeze_available"] is True
    assert report["failing_candidates"] == 2
    assert frozen["path"] == "examples/improvable-uppercase-skill/.clawreinforce/regressions.jsonl"
    assert len(frozen["added"]) == 2
    assert certified["report"]["tiers"][0]["coverage"]["expected"] == 3


def test_model_provider_discovery_http_returns_table_fields(tmp_path: Path) -> None:
    with api_server(tmp_path) as base:
        result = request(base, "/api/models/discover", {"provider": "fixture"})
    fixture = next(row for row in result["providers"] if row["provider"] == "fixture")
    assert {key: fixture[key] for key in ("configured", "key_source", "last_error")} == {
        "configured": True,
        "key_source": "built_in",
        "last_error": None,
    }
    openai = next(row for row in result["providers"] if row["provider"] == "openai")
    assert {key: openai[key] for key in ("configured", "key_source", "state")} == {
        "configured": False,
        "key_source": "none",
        "state": "key_missing",
    }
    assert result["discovery"] == {"provider": "fixture", "status": "completed", "error": None}
    assert fixture["models"] == ["echo", "upper-if-skilled"]


def test_initial_model_catalog_never_calls_remote_discovery(tmp_path: Path) -> None:
    app = AppState(tmp_path, ROOT / "web")

    def unexpected(provider: str):
        raise AssertionError(f"initial catalog tried to discover {provider}")

    app.providers.discover = unexpected
    catalog = app.model_catalog()
    assert catalog["models"] == [
        {"provider": "fixture", "model": "echo", "tier": "fixture:echo"},
        {"provider": "fixture", "model": "upper-if-skilled", "tier": "fixture:upper-if-skilled"},
    ]
    with api_server(tmp_path) as base:
        with urllib.request.urlopen(base + "/api/models", timeout=5) as response:
            assert response.headers["Cache-Control"] == "no-store"
        with urllib.request.urlopen(base + "/", timeout=5) as response:
            assert response.headers["Cache-Control"] == "no-cache"


def test_unknown_model_provider_error_is_structured(tmp_path: Path) -> None:
    with api_server(tmp_path) as base:
        try:
            request(base, "/api/models/discover", {"provider": "does-not-exist"})
        except urllib.error.HTTPError as exc:
            error = json.loads(exc.read())["error"]
        else:
            raise AssertionError("request should fail")
    assert error["code"] == "provider.unknown"
    assert error["context"] == {"provider": "does-not-exist"}
