import asyncio
import shutil
import sys
import time
from pathlib import Path

from clawreinforce.adapters.mcp_server import McpFacade


ROOT = Path(__file__).parents[1]


def test_mcp_facade_runs_zero_key_evidence_path(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "examples", tmp_path / "examples")
    facade = McpFacade(tmp_path)

    skills = facade.list_skills()
    assert skills["ok"]
    assert any(row["name"] == "incident-triage" for row in skills["result"]["skills"])
    assert facade.list_tasks()["ok"]
    assert facade.list_models()["result"]["preset"] == "fixture:reference"
    assert facade.scan_skill("examples/incident-triage-skill")["result"]["findings"] == []

    certified = facade.certify_skill("examples/incident-triage-skill", ["fixture:reference"])
    tier = certified["result"]["report"]["tiers"][0]
    assert tier["coverage"] == {"completed": 10, "expected": 10, "passed": 10}
    assert tier["pass_rate"] == 1.0
    certificate = certified["result"]["certificate"]
    fingerprint = certified["result"]["report"]["fingerprint"]
    assert facade.verify_certificate(certificate, fingerprint)["result"] == {
        "valid": True,
        "message": "valid",
    }
    assert facade.guard_skill("examples/incident-triage-skill", ["fixture:reference"])["result"]["verdict"] == "install"

    improve_path = tmp_path / "examples" / "improvable-uppercase-skill" / "SKILL.md"
    original = improve_path.read_text(encoding="utf-8")
    improved = facade.improve_skill_dry_run(
        "examples/improvable-uppercase-skill",
        "fixture:upper-if-skilled",
        ["fixture:upper-if-skilled"],
        "instruct",
        1,
    )
    assert improved["ok"]
    assert improved["result"]["accepted"]
    assert improve_path.read_text(encoding="utf-8") == original

    started = facade.start_bench(
        "examples/incident-triage-task",
        "examples/incident-triage-skill",
        ["fixture:reference"],
        2,
    )
    run_id = started["result"]["run_id"]
    deadline = time.monotonic() + 5
    state = facade.get_run(run_id)
    while state["ok"] and not state["result"]["finished"] and time.monotonic() < deadline:
        time.sleep(0.01)
        state = facade.get_run(run_id)
    assert state["result"]["finished"]
    terminal = state["result"]["events"][-1]
    assert terminal["type"] == "run_completed"
    assert terminal["report"]["summary"]["uplift"] == 1.0

    missing = facade.get_run("missing")
    assert not missing["ok"]
    assert missing["error"]["code"] == "run.not_found"


def test_mcp_stdio_lists_judge_tools(tmp_path: Path) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    shutil.copytree(ROOT / "examples", tmp_path / "examples")

    async def inspect() -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "clawreinforce", "mcp", "--project", str(tmp_path)],
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                assert {
                    "health",
                    "list_skills",
                    "list_tasks",
                    "list_models",
                    "scan_skill",
                    "certify_skill",
                    "guard_skill",
                    "start_bench",
                    "get_run",
                    "improve_skill_dry_run",
                    "verify_certificate",
                } <= names
                result = await session.call_tool("health", {})
                assert not result.isError

    asyncio.run(inspect())
