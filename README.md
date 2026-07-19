# clawreinforce

> CI for agent skills: fetch, inspect, certify, compare, and decide before an agent installs a skill.

This is the fresh OpenAI Build Week rebuild. The product keeps deterministic checks in a pure Python core, exposes the same contract through CLI and HTTP, and uses a four-area web UI for Verify, Improve, Arena, and Models.

## Start the hackathon demo

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\clawreinforce.exe serve --project . --port 8788
```

Open [http://127.0.0.1:8788](http://127.0.0.1:8788).

The Models tab discovers the enabled provider's current model catalog automatically. The API key stays on the server and is never returned to the browser.

## Ollama Cloud

The preferred setup is an environment variable:

```powershell
$env:OLLAMA_API_KEY = "your-key"
.\.venv\Scripts\clawreinforce.exe models --project . --discover ollama-cloud
```

For a project-local setup, create `.clawreinforce/providers.json`:

```json
{
  "openai": { "enabled": false },
  "anthropic": { "enabled": false },
  "ollama": { "enabled": false },
  "ollama-cloud": {
    "enabled": true,
    "api_key": "your-key"
  }
}
```

`.clawreinforce/` is ignored by Git. Test discovery and one minimal request:

```powershell
.\.venv\Scripts\clawreinforce.exe models --project . --discover ollama-cloud
.\.venv\Scripts\clawreinforce.exe models --project . --probe ollama-cloud:gpt-oss:20b
```

## Link-first workflow

ClawHub page URLs work directly:

```powershell
.\.venv\Scripts\clawreinforce.exe guard "https://clawhub.ai/jaaneek/skills/x-search" --tier ollama-cloud:gpt-oss:20b
```

SkillsBench accepts both the public website and GitHub task folder:

```powershell
.\.venv\Scripts\clawreinforce.exe task-check "https://www.skillsbench.ai/tasks/3d-scan-calc"
.\.venv\Scripts\clawreinforce.exe task-check "https://github.com/benchflow-ai/skillsbench/tree/main/tasks/edit-pdf"
```

The UI includes the requested presets:

- Easy: `court-form-filling`
- Medium: `edit-pdf`
- Hard: `3d-scan-calc`

Website links are convenient for people. GitHub tree links are better for imports, and a GitHub URL pinned to a commit SHA is best for reproducible benchmark evidence. Website task links are normalized to the official SkillsBench GitHub folder automatically.

## Honest benchmark boundary

Native `task.json` tasks use clawreinforce's deterministic checks and produce scores. SkillsBench tasks import their prompt, metadata, files, and difficulty, but their official container verifier is not executed by this lightweight runner. Those rows are marked `ungraded`; clawreinforce never converts missing verifier coverage into a zero or a fabricated score.

Many SkillsBench tasks also require files, GUI actions, or a sandboxed agent runtime. A plain cloud chat completion proves provider connectivity, not full task completion. Integrating the official SkillsBench execution environment is the next production milestone.

The `agent` check kind is **single-shot (no tool loop yet)**. It grades one emitted artifact map with the same hidden-grader path as `task`; it does not run an iterative agent or tool-calling loop.

## Useful commands

```powershell
# Local deterministic fixtures
.\.venv\Scripts\clawreinforce.exe scan examples\hello-skill
.\.venv\Scripts\clawreinforce.exe certify examples\hello-skill --tier fixture:echo
.\.venv\Scripts\clawreinforce.exe bench examples\uppercase-task examples\uppercase-skill --tier fixture:upper-if-skilled --trials 2

# Test suite
.\.venv\Scripts\python.exe -m pytest -q
```

## Architecture

```text
src/clawreinforce/core/       pure verification, fetching, grading, certificates
src/clawreinforce/adapters/   CLI, provider clients, HTTP, SSE run broker
web/                          HTTP-only browser client
tests/                        deterministic unit and integration tests
examples/                     small test fixtures, not installed user skills
```

Security properties include ZIP path validation, temporary remote-source staging, subprocess time/output limits, append-only JSONL ledgers, content fingerprints, and Ed25519-signed certificates. Provider failures stay structured and coverage-aware.

## Three-minute demo

1. Open Models and show the live Ollama Cloud catalog.
2. Select a model and send it to Verify or Arena.
3. Paste the ClawHub X Search URL and run Guard.
4. Switch Arena between Easy, Medium, and Hard SkillsBench links.
5. Show that external verifier coverage is `ungraded`, then run the local uppercase fixture to demonstrate measurable `+1.00` uplift and SSE progress.
