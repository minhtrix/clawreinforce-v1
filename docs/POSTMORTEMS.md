# Build Week rebuild postmortems

This is the failure memory for a future clawreinforce rebuild. It records incidents that
are visible in the commit history or the current product. It deliberately does not turn
every feature iteration into a “bug.” Each item ends with a guardrail that can be tested
in a clean rebuild.

## PM-01 — Product claims outran implementation

- **Symptom:** `agent` was accepted as a check kind although it was only the same
  single-shot artifact grader as `task`; the name suggested an iterative tool loop.
- **Cause:** the public noun was chosen before the execution boundary was made explicit.
- **Fix:** help text, README, and check results now say “single-shot (no tool loop yet).”
- **Guardrail:** every public capability name gets an executable contract test and an
  explicit unsupported-boundary sentence before it enters the UI.
- **Evidence:** `e2848fb`.

## PM-02 — OpenAI-compatible did not mean OpenAI-identical

- **Symptom:** DeepSeek, vLLM, and LiteLLM-style endpoints could reject
  `max_completion_tokens`.
- **Cause:** the compatible transport inherited one provider-specific request field.
- **Fix:** send `max_tokens`; retry once with the alternate field only when a 400 body
  explicitly identifies the token-field mismatch.
- **Guardrail:** fake-transport tests cover both first-request success and the precise
  fallback path. Never retry unrelated 400 responses.
- **Evidence:** `b127e74`.

## PM-03 — The first GUI shell had controls without complete evidence flows

- **Symptom:** Verify, Improve, Arena, and Models looked like product areas before every
  control had a real HTTP path, honest errors, exports, or actionable empty states.
- **Cause:** the visual shell was built before tab-specific acceptance walkthroughs.
- **Fix:** each tab was completed independently: signed Verify evidence, honest Improve
  status, streamed Arena rows and exports, and provider discovery status.
- **Guardrail:** one commit per tab; before merge, walk the tab from an empty fresh clone
  using fixtures and assert that every control causes a visible state transition.
- **Evidence:** `69cf871`, `7e8dc46`, `bd4c2ad`, `8a92301`.

## PM-04 — “Partial” and `n/a` hid the most important fact

- **Symptom:** an Arena row could have no score and only say `partial`.
- **Cause:** availability, provider failure, cancellation, and unsupported external
  verifier were collapsed into one display state.
- **Fix:** every ungraded row carries a concrete reason in the row and exports; provider
  structured errors remain intact.
- **Guardrail:** a test must reject any result whose score is `None` and reason is empty.
- **Evidence:** `8a0ab3a`.

## PM-05 — Provider configuration and connectivity were conflated

- **Symptom:** users could not tell “key missing,” “configured but unreachable,” and
  “provider returned an error” apart. A broad connectivity probe then risked breaking
  stable zero-key flows and was reverted.
- **Cause:** configuration state, catalog discovery, and live inference were treated as
  one operation.
- **Fix:** expose configured/key source/last error separately; discover explicitly;
  preserve the rollback rather than shipping an unfinished probe.
- **Guardrail:** provider listing is local and side-effect free. Network discovery is an
  explicit action, and fixture walkthrough tests run with all remote calls forbidden.
- **Evidence:** `f331c4d`, `95bad76`, `24df8c6`, `9601b5f`.

## PM-06 — A zero-key demo accidentally depended on remote state

- **Symptom:** the fixture walkthrough could trigger provider discovery or otherwise
  depend on configured remote APIs.
- **Cause:** page initialization coupled catalog freshness to the core demo path.
- **Fix:** fixtures and the fresh-clone walkthrough are independent from network and keys.
- **Guardrail:** run the full fixture journey with a transport that raises on any network
  access.
- **Evidence:** `993b6cf`.

## PM-07 — “Model” meant two different things

- **Symptom:** deterministic fixtures such as Echo and Upper-if-skilled appeared to users
  as selectable “models,” while real LLMs were hidden behind typed fields or discovery.
- **Cause:** test executors and LLM model catalogs shared one undifferentiated picker.
- **Fix:** preload provider-grouped real LLM catalogs, keep fixtures in a visibly separate
  “not LLMs” group, and make Author/Breaker versus Gate roles the first workflow step.
- **Guardrail:** model-picker tests assert provider groups, fixture labeling, selected
  counts, role semantics, and a usable default that is a real LLM when available.
- **Evidence:** `e6fd121`, `7492480`, `584f650`, `9d1ab2e`, `0f73e5f`.

## PM-08 — Improve initially proved a gate, not a product loop

- **Symptom:** the gates existed but there was no end-to-end orchestration, model matrix,
  persisted evidence, iteration history, or before/after artifact view.
- **Cause:** acceptance logic was implemented before workflow and evidence design.
- **Fix:** deterministic grade → propose → re-grade → gate flow; multi-model author/gates;
  dry-run/apply; persisted evidence; iteration history and hardening output.
- **Guardrail:** every attempt records proposal, per-model before/after, decision reasons,
  diff, token/cost data when available, and file truth. Rejected attempts never mutate.
- **Evidence:** `5a63fab`, `4881933`, `39c56dd`, `164a402`, `3df3755`, `e07a706`.

## PM-09 — Adversarial explanations were initially too easy to over-trust

- **Symptom:** “why did this fail?” risked becoming an unverified model explanation.
- **Cause:** breaker hypotheses and deterministic reproduction were not separated.
- **Fix:** Trap Lab treats rationales as untrusted, executes every safe candidate on every
  selected gate model, shows expected versus actual, and freezes only reviewed failures.
- **Guardrail:** never score a rationale. Only reproducible deterministic failures can be
  selected, and persistence requires an explicit review action.
- **Evidence:** `6e04534`, `1b7be53`, `0e705f2`.

## PM-10 — Remote-source support was broader than local execution support

- **Symptom:** a SkillsBench link could import successfully although its container
  verifier could not be executed by the light runner; ClawHub source expectations were
  also unclear in Trap Lab.
- **Cause:** fetchability, gradeability, and product support were presented as one fact.
- **Fix:** normalize supported URLs, disclose remote-source boundaries, and mark imported
  container-verifier tasks as ungraded with a useful reason.
- **Guardrail:** every catalog item declares source support, required capabilities, grader
  type, and whether this runtime can produce an official score.
- **Evidence:** `c8e8d81`, source and Arena reason tests.

## PM-11 — Arena summaries could overstate evidence

- **Symptom:** partial runs could count as solved, a fixture looked like the default model,
  and the inference-call budget was not visible before launch.
- **Cause:** presentation aggregates were designed without explicit coverage invariants.
- **Fix:** exclude partial runs from solved counts, default the model hub to a real LLM,
  show the call budget, and explain model-by-model uplift.
- **Guardrail:** every aggregate carries a denominator and coverage; unavailable is never
  converted to zero or success; cost/call estimates appear before remote execution.
- **Evidence:** `5a758ca`, `0f73e5f`, `89b550b`, `3975734`.

## PM-12 — The shipped examples demonstrate plumbing, not value

- **Symptom:** `hello-skill` echoes text, `uppercase-skill` uppercases one case, and
  `improvable-uppercase-skill` is deliberately wrong. They produce obvious uplift but
  make the product look trivial.
- **Cause:** deterministic fixtures were promoted into the public demo role.
- **Status:** open. Keep these three under a clearly labeled fixture/smoke-test group.
- **Guardrail:** the public demo must contain at least three non-trivial, frozen tasks with
  8–12 cases each, multiple failure modes, cross-model results, and no fabricated target
  percentage. Select tasks whose measured baseline leaves honest improvement headroom.

## Cross-cutting rebuild rules

1. Preserve a green, tagged submission branch before any redesign or rebuild.
2. Core invariants and structured errors precede adapters and UI.
3. Test every step and commit only green, behavior-described increments.
4. Fixtures prove determinism; flagship scenarios prove user value. Never mix the labels.
5. Fetchable, executable, gradeable, and officially comparable are separate capabilities.
6. Missing coverage is `n/a` plus a reason, never an invented zero.
7. Remote calls require a visible call/cost estimate and an explicit user action.
8. Long operations emit real phase events; never animate fake progress.
9. Freeze golden and adversarial cases before measuring uplift.
10. Run a fresh-clone, zero-key demo and a configured-provider smoke test before release.
