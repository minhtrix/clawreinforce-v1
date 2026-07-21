# Agent quickstart — MCP

clawreinforce exposes the same core evidence flows to Codex and other MCP clients over
stdio. The MCP adapter does not duplicate scoring logic and does not expose an `apply`
or trap-freeze mutation tool.

## Install

From the repository root:

```console
python -m venv .venv
python -m pip install -e ".[mcp]"
```

The server command is:

```console
python -m clawreinforce mcp --project /absolute/path/to/clawreinforce
```

It speaks MCP on standard input/output, so start it through an MCP client rather than
typing into that process.

## Connect Codex

Codex CLI, the IDE extension, and the desktop app share MCP configuration. Add a stdio
server in the desktop app under **Settings → MCP servers → Add server**, or add the
matching block to `~/.codex/config.toml`. Use absolute paths so the server remains
independent of the task's current directory.

Windows:

```toml
[mcp_servers.clawreinforce]
enabled = true
required = false
command = "C:\\absolute\\path\\clawreinforce\\.venv\\Scripts\\python.exe"
args = ["-m", "clawreinforce", "mcp", "--project", "C:\\absolute\\path\\clawreinforce"]
startup_timeout_sec = 15.0
tool_timeout_sec = 180.0
```

macOS/Linux:

```toml
[mcp_servers.clawreinforce]
enabled = true
required = false
command = "/absolute/path/clawreinforce/.venv/bin/python"
args = ["-m", "clawreinforce", "mcp", "--project", "/absolute/path/clawreinforce"]
startup_timeout_sec = 15.0
tool_timeout_sec = 180.0
```

Restart Codex after saving, then use `/mcp` or `codex mcp list` to confirm that the
server initialized. Project-local `.codex/config.toml` is also supported after the repo
is trusted, but it cannot contain one portable virtual-environment path for all three
operating systems. See the current [Codex MCP documentation](https://developers.openai.com/codex/mcp/).

## Five-minute zero-key judge flow

Paste this into Codex after the server is connected:

```text
Use only the clawreinforce MCP tools.
1. List skills, tasks, and models. Explain which entries are real LLMs and which are fixtures.
2. Scan examples/incident-triage-skill.
3. Certify it with tiers=["fixture:reference"] and samples=1. Report coverage, pass rate, and fingerprint.
4. Guard the same skill with tiers=["fixture:reference"]. Explain the verdict and reasons.
5. Start a bench with task=examples/incident-triage-task, skill=examples/incident-triage-skill,
   tiers=["fixture:reference"], trials=2. Poll get_run until finished, then report
   without-skill, with-skill, uplift, and coverage from the terminal event.
6. State clearly what this deterministic reference proves and what still requires real LLM evidence.
```

Expected evidence:

- scan has no static findings;
- certification completes 10/10 cases at 100%;
- Guard returns `install` with no blocking reasons;
- Arena reports `0.0 → 1.0`, uplift `+1.0`, coverage `2/2`;
- the agent says `fixture:reference` is a deterministic test double, not an LLM.

## Tool boundary

- `list_skills`, `list_tasks`, and `list_models` are local and do not discover remotes.
- `discover_models` is the explicit network action for one provider.
- `scan_skill` may fetch a URL when the source is remote.
- `certify_skill`, `guard_skill`, and `improve_skill_dry_run` call every selected tier;
  remote tiers may incur provider cost.
- `start_bench` returns immediately with a run ID; `get_run` returns accumulated events.
- `certify_skill` creates local signing material; `improve_skill_dry_run` appends evidence
  to the ignored ledger but never changes `SKILL.md`.
- Every tool returns `{ok, result}` or `{ok: false, error}`. Missing coverage remains
  unavailable/partial with a structured reason rather than becoming a zero.
