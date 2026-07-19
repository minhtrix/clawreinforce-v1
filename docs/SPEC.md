# Master-Rebuild-Prompt für Codex + GPT-5.6 (OpenAI Build Week)

Dieses Dokument IST der Prompt: den Block unten komplett in die erste Codex-Session geben.
Er enthält das volle Feature-Inventar des bestehenden clawreinforce_vx, die Architektur-Invarianten
und den Build-Week-Scope — aber KEIN Design (GPT-5.6 gestaltet die Oberfläche neu) und bewusst
weder MCP-Adapter noch RedstoneLM (beides später nachrüstbar, siehe [README](../README.md)).

---

```
You are rebuilding **clawreinforce** from scratch as a Build Week project. You have full
architectural freedom on UI design and code organization details, but the PRODUCT SPEC and
INVARIANTS below are fixed. Work in small verified increments; every slice ends with green
tests and a runnable demo path.

# WHAT THIS PRODUCT IS (one paragraph)

Agents (OpenClaw, Claude Code, Codex) load "skills" — Markdown instructions plus scripts —
and execute them blindly. clawreinforce is **CI for agent skills**: it scans them statically,
attacks them with adversarial scenarios in isolation, certifies them against deterministic
checks across model tiers, and hardens them with gated self-rewrites. The trust artifact is a
**signed certificate + SVG badge** bound to the skill's content fingerprint. Tagline:
"No agent should run a skill nobody verified."

# THE TWO LOOPS (get the naming right — the old repo confused users here)

Everything is one principle — **the LLM proposes, deterministic code judges** — applied to two
signal sources:

1. **IMPROVE loop (skill-internal signal):** the skill has its own golden cases
   (input + deterministic check). A breaker LLM invents NEW checkable traps; failures become
   frozen regressions; a rewriter LLM proposes a new skill body; the gate accepts ONLY if the
   failing case turns green AND no previously-green case breaks — otherwise revert.
   Rewrite strategies: `instruct` (rewrite the rules) and `fewshot` (mine examples from real
   failures, VERIFY each example against the case's check before it may enter the body).
   Measured fact to encode in docs: fewshot wins when the same model mines and executes;
   instruct-style rules transfer better to foreign executor models.
2. **ARENA loop (task-external signal):** a benchmark task with a hidden grader measures
   models WITH vs WITHOUT the skill as equipment (uplift). The same gated rewrite, but the
   gate is the graded mean_score rising (optionally strict: no single model may regress).

UI naming (fixed): **verify** (scan · certify · badge · guard), **improve** (golden loop),
**arena** (bench + uplift hardening), **models** (provider hub). Do not use the old ambiguous
tab names "harden"/"reinforce".

# INVARIANTS (non-negotiable)

- Layering: `core/` = pure domain logic, no HTTP/UI imports, fully unit-testable.
  `adapters/http` + `adapters/cli` = thin mappings of the SAME core functions. `web/` = GUI,
  client of HTTP only, zero business logic. (No MCP adapter this week — but because the
  contract lives in core, an MCP adapter must be addable later as a thin file. Never put
  logic where only one surface can reach it.)
- **Isolation:** skill/agent code and model-emitted code run ONLY in an ephemeral temp dir
  subprocess with time/output limits — never in-process, never in the real project.
  `dry_run` never executes code.
- **Determinism at the gate:** no LLM-as-judge anywhere in scoring. Checks are code:
  equals/contains/not_contains/regex/property, `exec` (run emitted code, pass = exit 0),
  `task` (multi-file emit + author-hidden grader script), `agent` (iterative
  write_file/run_command tool loop, then same grader). Author-provided grader files always
  override model-emitted files.
- **Honest failure:** a missing API key, unreachable provider, or crashed run is its own
  status — NEVER counted as 0%. Every score displays its coverage (which cases, how many
  samples). No score without coverage.
- **Canonical store:** skill files on disk + append-only JSONL ledgers under
  `.clawreinforce/` (certs, regressions, bench runs). Reports/GUI are projections.
- **Multi-window truth:** long runs stream Server-Sent Events (run started, per-model row,
  progress, accepted/rejected iteration); any window reconstructs state from the stream.
- Max ~300 lines per file, one responsibility per file, tests in the same commit as the
  feature. Structured errors (code, kind, message, context) surfaced verbatim in every UI.
- Providers: Anthropic + OpenAI + Ollama + any OpenAI-compatible base_url (vLLM/LiteLLM
  keyless local). Keys from env first, then a git-ignored local JSON store the server loads
  at app construction (not only in one entrypoint). GPT-5.x rejects `max_tokens` → retry
  once with `max_completion_tokens`. Surface provider errors as `last_error`, never swallow.

# FEATURE INVENTORY (parity target from the old repo; build in the M-order below)

verify: scan (static issues incl. bloat/scope findings) · certify (golden cases × tiers
`provider:model`, `--samples k` reliability, pass_rate per tier) · signed cert (Ed25519,
bound to fingerprint, offline `cert-verify`, exit 1 in CI on tamper) · SVG badge (scope-
bearing text, never a bare "verified") · **guard** = fetch a skill from a ClawHub slug or
GitHub URL → scan → certify if golden cases exist → deterministic verdict
install|review|reject + badge (the "verify before install" command — this is the demo
centerpiece) · task-criteria view ("what is measured": rubric NAMES and run/expect shape,
never hidden grader source).

improve: breaker/traps (LLM invents checkable {input,check} traps, degenerate-check filter,
freeze into regressions ledger; effective suite = declared + frozen) · gated rewrite with
`instruct` | `fewshot` strategies (fewshot mines from failing cases, verifies every exemplar
via the real check, idempotent "## Examples (verified)" block) · loop until saturation with
per-iteration diffs and accept/reject reasons.

arena: bench = task × models × k trials, phases with/without skill, uplift delta ·
live per-model rows streamed into the RESULTS grid as each model finishes · cooperative
cancel keeping partial results · cost/token totals (unknown paid price = unknown, not $0) ·
persistence to ledger + history view · CSV + PNG export of results · certify-a-bench-result
(signed cert referencing the ledger entry) · uplift hardening (bench-gated rewrite,
`strict` per-model regression option, target_score early stop) · task import (task.md /
skillsbench-style repos, assets) · **task author wizard with auto-eval**: creating a task
requires an oracle solution; the hidden grader is smoke-run against the oracle — if the
oracle can't pass, the task is broken (red with reason), plus a health traffic light in the
task picker.

models: provider registry + key status (source env|file, never the key value) · model
discovery via provider APIs · local endpoints (vLLM/LiteLLM) keyless · grouped, filterable
model pickers (must stay readable with 100+ models).

# GPT-5.6 IS ALSO A PRODUCT FEATURE

Ship a first-class "certify on GPT-5.6" tier preset and a "GPT-5.6 verified" badge variant.
The README must show both: Codex built the repo, AND GPT-5.6 runs inside the product as a
certification tier + as an arena executor.

# BUILD ORDER (each M ends demoable; cut from the back if time runs out)

M1 core spine (CLI-first): skill model + fingerprint · scan · golden certify (text checks +
   exec) · signed cert + verify · badge · ledger · providers (env + local store).
M2 guard + GPT-5.6 tier: fetch (ClawHub/GitHub) → guard verdict pipeline · tier presets ·
   the demo script "guard a real ClawHub skill in one command".
M3 arena: task/agent checks · bench with SSE live rows · cancel · costs · history ·
   CSV export · bench-certify. GUI shell with the four tabs goes live here.
M4 improve + author flow: traps → gated rewrite (instruct + fewshot) · task wizard with
   oracle smoke-run · PNG export · polish, empty states, error surfaces.
Cut candidates (roadmap, not this week): Docker stage-2 isolation, Playwright env,
property-based checks, postmortem records, parallel bench execution.

# POSITIONING (put this in the README — it matters)

ClawBench (github.com/openclaw/shellbench) benchmarks **models** as OpenClaw agents on a
fixed curated task suite (completion/trajectory/behavior/reliability, pass^k, deterministic
verification, advisory-only LLM judge). We share its verification philosophy — verify the
work, never trust the transcript, deterministic official scores — and cite it respectfully.
The difference is the unit: **ClawBench ranks models; this tool certifies and improves
SKILLS.** It measures a skill's uplift (same model WITH vs WITHOUT the skill), gates
self-rewrites, and issues fingerprint-bound signed certificates — and it changes the
artifact, not just scores it. One sentence for the README: "ClawBench tells you which model
to run. clawreinforce tells you which skills to trust — and makes them better. Agents need
both."

# QUALITY BAR FOR JUDGING

Working > feature count. Every demo path must run on a fresh clone with documented setup.
README sections: what it is (agent-skill trust problem) · quickstart · how Codex was used
(sessions, what it built) · how GPT-5.6 was used (build + in-product tier) · architecture ·
positioning vs ClawBench (above) · measured evidence (include the instruct-vs-fewshot A/B
numbers from docs/experiments/fewshot-ab.md of the predecessor repo as design rationale).
```

---

Ende des Master-Prompts. Session-Kickoff, Arbeitsmuster und die Extend-vs-Rebuild-Entscheidung
stehen in der [Produkt-README](../README.md).
