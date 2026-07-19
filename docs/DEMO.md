# Three-minute demo

## Setup before the timer

From a fresh clone, install the editable package. No API key is needed for the deterministic path.

```console
python -m pip install -e .
```

Run the presenter script from the repository root:

```powershell
.\demo\demo.ps1
```

If Windows PowerShell blocks local scripts by policy, use a process-local bypass (it does not change the machine policy):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\demo\demo.ps1
```

```bash
./demo/demo.sh
```

Use `-SkipServe` / `--skip-serve` for automated verification. Use `-SkipLiveGuard` / `--skip-live-guard` only when the machine has no network access.

## 0:00–0:35 — real input, honest review

```console
clawreinforce guard https://clawhub.ai/jaaneek/skills/x-search --tier openai:gpt-5.6-sol
```

Expected signal:

```text
verdict: review
reasons: ["skill has no golden cases"]
certification: null
```

Say: “The source is real and fetched from ClawHub. Missing tests do not become a zero or a pass; they become review.”

Important correction to the original storyboard: this exact no-cases path short-circuits before provider execution. It does **not** consume `OPENAI_API_KEY`; its API cost is **$0.00**. The scripts optionally run this separate paid connectivity proof when `OPENAI_API_KEY` exists:

```console
clawreinforce models --project . --probe openai:gpt-5.6-sol
```

That short probe is normally under $0.01. The estimate uses current standard GPT-5.6 Sol rates of [$5 per 1M input tokens and $30 per 1M output tokens](https://developers.openai.com/api/docs/models/gpt-5.6-sol); actual cost follows metered tokens. This probe is the only key-requiring command in the demo.

## 0:35–1:15 — deterministic certificate and badge

```console
clawreinforce certify examples/uppercase-skill --tier fixture:upper-if-skilled
clawreinforce badge demo-output/uppercase-certificate.json --output demo-output/uppercase-badge.svg
```

Expected signal:

```text
status: completed
coverage: 1 / 1
pass_rate: 1.0
artifacts: demo-output/uppercase-certificate.json, demo-output/uppercase-badge.svg
```

Say: “The signature binds this result to the exact skill fingerprint. No key or network was used.”

## 1:15–1:55 — measured uplift and exports

```console
clawreinforce bench examples/uppercase-task examples/uppercase-skill \
  --tier fixture:upper-if-skilled --trials 2 \
  --csv demo-output/arena.csv --png demo-output/arena.png
```

PowerShell can use the same command on one line. Expected signal:

```text
without_skill: 0.0
with_skill: 1.0
uplift: 1.0
coverage: 2 / 2
artifacts: demo-output/arena.csv, demo-output/arena.png
```

Say: “Same task, same executor, skill off and on. The delta is the product.”

## 1:55–2:55 — four-tab GUI

```console
clawreinforce serve --project . --host 127.0.0.1 --port 8788
```

Open [http://127.0.0.1:8788](http://127.0.0.1:8788), then show:

1. **Verify (20s):** select `uppercase-skill` and `fixture:upper-if-skilled`; point to findings, 1/1 coverage, fingerprint, signature check, badge, then the install verdict.
2. **Improve (10s):** select `improvable-uppercase-skill`, keep `fixture:upper-if-skilled` and `instruct`, then run the dry-run. Show the failing case turning green, the accepted unified diff, and the zero-regression gate reason.
3. **Arena (20s):** run two fixture trials; rows arrive from SSE, uplift becomes `+1.00`, and CSV/PNG downloads activate.
4. **Models (10s):** show `configured`, `key_source`, `last_error`, then click **Discover fixture**. No secret value is rendered.

Finish before 3:00: “No agent should run a skill nobody verified.”

## Automated zero-key verification

```powershell
.\demo\demo.ps1 -SkipLiveGuard -SkipOpenAIProbe -SkipServe
```

```bash
./demo/demo.sh --skip-live-guard --skip-openai-probe --skip-serve
```

Both scripts fail if certification is not 100%, uplift is not +1.0, or any expected artifact is missing.
