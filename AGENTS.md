# AGENTS.md — clawreinforce

Read this file before changing the project.

## Product truth

clawreinforce is CI for agent skills. It fetches untrusted skills, scans them, runs declared deterministic cases, measures skill uplift, and emits fingerprint-bound trust artifacts.

Code is authoritative. Missing provider or verifier coverage must remain `None`/`ungraded`; never turn unavailable coverage into a zero score.

## Entry points

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\clawreinforce.exe serve --project . --port 8788
```

- CLI: `src/clawreinforce/adapters/cli.py`
- HTTP/SSE: `src/clawreinforce/adapters/http.py`
- Providers: `src/clawreinforce/adapters/providers.py`
- Domain core: `src/clawreinforce/core/`
- Browser client: `web/`

## Architecture rules

- `core/` must not import UI or transport modules.
- CLI and HTTP are thin adapters over the same core functions.
- The web client talks only to HTTP endpoints.
- Run untrusted executable checks only through the bounded temporary subprocess path.
- Keep files at or below 300 lines.
- Add or update tests in the same change.
- Delete superseded code and generated artifacts.

## Remote inputs

- Skills: local paths, GitHub tree URLs, ClawHub slugs, or canonical ClawHub page URLs.
- Tasks: local folders, GitHub tree URLs, or `skillsbench.ai/tasks/<slug>` URLs.
- SkillsBench website links normalize to the official GitHub task folder.
- External SkillsBench verifiers are not part of the lightweight runner; report them as ungraded.

## Secrets

Use environment variables when possible. Local provider settings belong only in ignored `.clawreinforce/providers.json`. Never return API keys through HTTP, logs, certificates, ledgers, or test fixtures.

