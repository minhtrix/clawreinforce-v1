from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from clawreinforce.adapters.http_arena import BenchManager, task_catalog
from clawreinforce.adapters.http_improve import improve_source
from clawreinforce.adapters.http_verify import (
    certify_source,
    check_certificate,
    guard_source,
    scan_source,
    skill_catalog,
)
from clawreinforce.adapters.model_catalog import ModelCatalog
from clawreinforce.adapters.providers import ProviderHub
from clawreinforce.adapters.run_broker import RunBroker
from clawreinforce.errors import ClawError


class McpFacade:
    """Structured, SDK-independent tool facade shared by MCP and tests."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.providers = ProviderHub(self.project_root)
        self.models = ModelCatalog(self.providers)
        self.runs = RunBroker()
        self.bench = BenchManager(self.project_root, self.providers, self.runs)

    def health(self) -> dict[str, Any]:
        """Check that the local clawreinforce project adapter is ready."""
        return self._safe(lambda: {"status": "ok", "product": "clawreinforce", "project": str(self.project_root)})

    def list_skills(self) -> dict[str, Any]:
        """List local skill fixtures and flagship packs with category and case count."""
        return self._safe(lambda: skill_catalog(self.project_root))

    def list_tasks(self) -> dict[str, Any]:
        """List native gradeable tasks and clearly marked external task references."""
        return self._safe(lambda: task_catalog(self.project_root))

    def list_models(self) -> dict[str, Any]:
        """List configured providers and cached models without performing network discovery."""
        return self._safe(self.models.catalog)

    def discover_models(self, provider: str) -> dict[str, Any]:
        """Explicitly discover one provider's model catalog; this may use the network."""
        return self._safe(lambda: self.models.discover(provider))

    def scan_skill(self, source: str) -> dict[str, Any]:
        """Statically scan a local path, GitHub URL, or ClawHub skill source."""
        return self._safe(lambda: scan_source(self.project_root, source))

    def certify_skill(self, source: str, tiers: list[str], samples: int = 1) -> dict[str, Any]:
        """Run frozen deterministic cases and issue fingerprint-bound signed evidence."""
        return self._safe(
            lambda: certify_source(self.project_root, source, tiers, samples, self.providers.execute)
        )

    def guard_skill(self, source: str, tiers: list[str], samples: int = 1) -> dict[str, Any]:
        """Fetch, scan, certify, and return install/review/reject with reasons."""
        return self._safe(
            lambda: guard_source(self.project_root, source, tiers, samples, self.providers.execute)
        )

    def start_bench(
        self,
        task: str,
        skill: str,
        tiers: list[str],
        trials: int = 2,
    ) -> dict[str, Any]:
        """Start same-model without-skill versus with-skill trials and return a run ID."""
        return self._safe(
            lambda: {
                "run_id": self.bench.start(
                    {"task": task, "skill": skill, "tiers": tiers, "trials": trials},
                    "fixture:reference",
                ).run_id
            }
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Get accumulated bench events and terminal state for a run ID."""
        def operation() -> dict[str, Any]:
            state = self.runs.get(run_id)
            if state is None:
                raise ClawError("run.not_found", "not_found", "run was not found", run_id=run_id)
            return {
                "run_id": run_id,
                "events": state.events,
                "finished": state.finished,
                "cancelled": state.cancelled,
            }

        return self._safe(operation)

    def improve_skill_dry_run(
        self,
        source: str,
        author_tier: str,
        gate_tiers: list[str],
        strategy: str = "instruct",
        max_rewrites: int = 3,
    ) -> dict[str, Any]:
        """Propose and gate rewrites without changing SKILL.md; evidence is appended to the ledger."""
        return self._safe(
            lambda: improve_source(
                self.project_root,
                source,
                author_tier,
                strategy,
                max_rewrites,
                False,
                self.providers.execute,
                author_tier=author_tier,
                gate_tiers=gate_tiers,
            )
        )

    def verify_certificate(self, certificate: dict[str, Any], fingerprint: str = "") -> dict[str, Any]:
        """Verify an Ed25519 certificate and optional expected skill fingerprint."""
        return self._safe(
            lambda: check_certificate({"certificate": certificate, "fingerprint": fingerprint or None})
        )

    @staticmethod
    def _safe(operation: Callable[[], Any]) -> dict[str, Any]:
        try:
            return {"ok": True, "result": operation()}
        except Exception as exc:
            if isinstance(exc, ClawError):
                error = exc.detail.to_dict()
            else:
                error = {"code": "mcp.failed", "kind": "runtime", "message": str(exc), "context": {}}
            return {"ok": False, "error": error}


def create_server(project_root: Path):
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise ClawError(
            "mcp.dependency_missing",
            "unavailable",
            "MCP support is not installed; run: python -m pip install -e '.[mcp]'",
        ) from exc

    facade = McpFacade(project_root)
    server = FastMCP(
        "clawreinforce",
        instructions=(
            "Verify agent skills with deterministic checks. Start with list_skills, list_tasks, and list_models. "
            "Fixtures are test doubles, not LLMs. Missing coverage is never a zero. Use start_bench then poll "
            "get_run until finished. improve_skill_dry_run never changes SKILL.md; remote tiers may cost money."
        ),
        json_response=True,
    )
    for tool in (
        facade.health,
        facade.list_skills,
        facade.list_tasks,
        facade.list_models,
        facade.discover_models,
        facade.scan_skill,
        facade.certify_skill,
        facade.guard_skill,
        facade.start_bench,
        facade.get_run,
        facade.improve_skill_dry_run,
        facade.verify_certificate,
    ):
        server.tool()(tool)
    return server


def run_mcp(project_root: Path) -> None:
    create_server(project_root).run(transport="stdio")
