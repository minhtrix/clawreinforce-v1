# Buildweek V2 — sequential rebuild prompts

These are ten independent prompts, not one master prompt. Use them in order in a clean
Codex task on a `buildweek-v2` branch or worktree. Keep the current green release tagged
and runnable until V2 passes the final fresh-clone gate. Every prompt must read
`docs/POSTMORTEMS.md` first and cite the postmortem IDs it prevents.

## Prompt 1 — Freeze evidence and establish the rebuild boundary

```text
Continue clawreinforce in this repository. First read AGENTS.md, docs/SPEC.md,
docs/POSTMORTEMS.md, README.md, and the current tests. Do not change product behavior.
Verify git status and the full test suite, record the current commit as the V1 baseline,
and create a V2 branch/worktree without deleting or rewriting V1 history. Add a concise
docs/V2_SCOPE.md that distinguishes inherited behavior, new Build Week work, explicit
non-goals, and the exact test/demo commands. Preserve ignored provider keys and signing
material. Run all tests and commit only if green with message:
"docs: freeze v1 evidence and define v2 boundary".
Acceptance: V1 remains directly runnable; V2 provenance is unambiguous; PM-01 and the
cross-cutting rebuild rules are referenced.
```

## Prompt 2 — Rebuild the domain contracts before surfaces

```text
Rebuild or refactor only the core domain layer for V2: Skill, GoldenCase, CheckSpec,
ProviderResult, certification reports, fingerprints, structured errors, coverage, and
append-only ledger events. Preserve the invariant that deterministic checks alone score
results, unavailable coverage is never zero, agent checks are explicitly single-shot,
and fetchable/executable/gradeable are separate capabilities. Add contract tests before
adapter changes. Do not touch the GUI. Run the whole suite and commit green with:
"refactor: establish v2 evidence contracts".
Acceptance: PM-01, PM-04, PM-10, and PM-11 cannot recur through the public types/tests.
```

## Prompt 3 — Providers and a real LLM catalog

```text
Implement the V2 provider boundary and model catalog. Support OpenAI, Anthropic, local
Ollama, Ollama Cloud, and configurable OpenAI-compatible endpoints. Listing providers
must be offline and show configured, key_source, and last_error. Discovery is explicit.
Use max_tokens first for compatible endpoints and only perform the tested one-time
alternate-key retry for the documented 400 mismatch. Preload known model IDs for useful
first paint, reconcile with discovery, group by provider, filter, bulk-select, and label
fixtures as deterministic test executors — not LLMs. Never expose secrets. Run all tests
and commit green with: "feat: provide honest selectable llm catalogs".
Acceptance: fixture-only tests forbid network; fake transports cover PM-02, PM-05,
PM-06, and PM-07.
```

## Prompt 4 — Verify and Guard as signed evidence

```text
Build the V2 Verify workflow through core, CLI, HTTP, and the no-framework UI. Support a
local path, GitHub tree URL, ClawHub slug, and canonical ClawHub URL. Provide skill picker,
scan findings, multi-model certification, per-tier coverage/pass rate, fingerprint-bound
certificate and signature verification, badge preview, and Guard verdict with reasons.
Render structured errors verbatim and make every empty state actionable. No remote call
may start without visible selected models and call count. Walk it with fixtures and one
configured provider when available. Run all tests and commit green with:
"feat: rebuild signed verify and guard evidence".
Acceptance: no dead controls; PM-03, PM-04, PM-06, and PM-10 are covered.
```

## Prompt 5 — Three flagship scenarios, not 200 shallow templates

```text
Keep hello/uppercase examples under a visible Fixtures / smoke tests label. Add exactly
three non-trivial flagship skill+task scenarios using capabilities the light runner truly
supports. Choose from structured incident triage, privacy-safe record transformation,
and API migration review. Give each 8–12 frozen golden cases spanning normal, edge,
conflict, and malformed inputs; use property/regex/exec checks where appropriate. Add
metadata for category, difficulty, grader type, required capabilities, and expected run
cost. Calibrate on fixtures plus at least three real LLMs when keys are available, but do
not hard-code or promise a desired uplift. Document measured baselines and confidence,
and prefer scenarios that honestly show improvement headroom. Run all tests and commit
green with: "feat: add credible measured skill scenarios".
Acceptance: the demo communicates real value and directly closes PM-12.
```

## Prompt 6 — Improve and Trap Lab with real event evidence

```text
Rebuild Improve as measure → propose → re-measure → gate. The user selects one real LLM
as Author/Breaker and one or more real LLMs as Gates/Focus; fixtures remain a separate
test option. Support instruct and verified-fewshot, max attempts, dry-run by default, and
apply only after a zero-regression gate. Emit real phase/attempt/model events, elapsed
time, token/cost data, baseline→best lines, reasons, unified diffs, iteration history,
learned patterns, and before/after skill bodies. Trap Lab may invent candidates but must
execute safe checks across every gate model; rationales remain untrusted and only
explicitly reviewed failures may be frozen. Run all tests and commit green with:
"feat: rebuild evidence-driven improve and traps".
Acceptance: PM-08 and PM-09 are enforced end to end; rejected attempts never mutate.
```

## Prompt 7 — Arena statistics and live comparability

```text
Rebuild Arena around same-model without-skill versus with-skill trials. Provide task,
skill, grouped multi-LLM, and trial selectors; show the exact remote call budget before
run. Stream a row as every trial completes, with real phase status, elapsed time, tokens,
cost, provider errors, cancellation, and honest n/a reasons. Aggregate per model with
baseline→equipped→uplift, Pass@1, Pass@k, Pass^k, confidence interval, coverage, improved,
regressed, and fully solved counts. Partial/unavailable rows must never enter solved
counts. CSV and PNG exports must contain the same evidence. Run all tests and commit
green with: "feat: rebuild live multi-model uplift arena".
Acceptance: PM-04, PM-10, and PM-11 have explicit regression tests.
```

## Prompt 8 — Thin agent-facing API and MCP

```text
Keep the existing core as the only source of truth. Document the HTTP API and add a thin
stdio MCP adapter, without duplicating domain logic. Expose only the judge-fast tools:
health, list_skills, list_tasks, list_models, scan, certify, guard, start_bench,
get_run/events, improve_dry_run, and verify_certificate. Long tools must return a run ID
or bounded result; errors stay structured; mutation requires an explicit apply/review
argument. Add `clawreinforce mcp`, installation instructions, supported platforms, and a
docs/AGENT_QUICKSTART.md containing a zero-key five-minute evaluation path. Add protocol
and clean-process tests. Run all tests and commit green with:
"feat: expose clawreinforce through a thin mcp adapter".
Acceptance: an automated judge can discover and test value without learning the GUI,
while PM-01 and PM-03 boundaries remain honest.
```

## Prompt 9 — Coherent high-signal UI and real progress

```text
Perform a no-framework UI/UX pass after all workflows work. Use a restrained translucent
visual system only where it improves hierarchy; preserve contrast, keyboard focus,
reduced motion, responsive layout, and dense evidence readability. Put model selection
first in Improve and Arena. Across all long operations show real event feed, phase
checklist, elapsed timer, empirical ETA range only when ledger data supports it,
intermediate results, cancel state, and completion summary. Never show fake percentage
progress. Apply the same result-card language, empty states, errors, model picker, and
cost line across tabs. Run browser walkthroughs at desktop and narrow widths, all tests,
and commit green with: "feat: unify v2 evidence and progress experience".
Acceptance: PM-03 and PM-07 are closed without hiding information behind decoration.
```

## Prompt 10 — Submission gate and fresh-clone proof

```text
Treat this as a release gate, not a feature prompt. On a new clean clone, install from
README, run the full test suite, run the complete zero-key fixture demo, run the three
flagship scenarios with any configured providers, test the HTTP API and MCP quickstart,
and walk Verify, Improve/Traps, Arena, and Models. Check that secrets and generated
evidence are ignored. Confirm every n/a has a reason, every remote run shows its call
budget, every mutation is explicit, and all demo claims match measured output. Update
README, docs/DEMO.md, docs/POSTMORTEMS.md, and the under-three-minute English storyboard
with exact outputs and Codex/GPT-5.6 provenance. If any gate fails, fix it before release
or keep V1 as the submission. Commit the green release with:
"release: prove v2 from a fresh clone".
Acceptance: no manual setup beyond documented keys; no claim depends on hidden state.
```

## Scope decision for the hackathon

- **Before submission:** finish assets and preserve the current green product; add only
  low-risk changes with direct judging value.
- **High-leverage candidates:** three flagship scenarios, agent quickstart/minimal MCP,
  and real Improve/Arena progress evidence.
- **Defer:** a 200-skill verified catalog, unsupported container/browser graders, and a
  full visual rewrite. A catalog manifest can come later without pretending every item
  has been measured.
- **Release rule:** V2 replaces V1 only after Prompt 10 passes. Otherwise V1 ships.
