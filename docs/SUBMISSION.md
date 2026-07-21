# OpenAI Build Week submission pack

This file is the copy-and-check source for the Developer Tools submission. Replace the
three bracketed values before submitting. Do not add claims that are not visible in the
video or reproducible from the repository.

## Required links and identifiers

- **Repository URL:** `[ADD REPOSITORY URL]`
- **Public YouTube demo (< 3:00):** `[ADD VIDEO URL]`
- **Primary Codex /feedback Session ID:** `[ADD SESSION ID]`
- **Category:** Developer Tools

If the repository is public, choose and add an appropriate license before submission.
If it remains private, share it with `testing@devpost.com` and
`build-week-event@openai.com` and verify access from a separate account.

## Title

clawreinforce — CI for agent skills

## Tagline

No agent should run a skill nobody verified.

## Short description

Agent skills are executable instructions, but today they are often installed on trust.
clawreinforce treats a skill like a software dependency: fetch it, scan it, run frozen
deterministic checks across selected LLMs, measure the same model with and without the
skill, and issue fingerprint-bound evidence. Its Improve and Trap workflows may propose
changes or adversarial cases, but only deterministic re-execution can accept them.

## Problem and impact

A plausible skill can silently make an agent worse, work only on its author's model, or
fail on one destructive edge case. A model-generated explanation is not sufficient
evidence. Developers need to know what was tested, which models completed coverage,
whether the skill caused uplift or regression, and whether the installed bytes still
match the reviewed artifact.

clawreinforce makes those questions testable in CI and before installation. It separates
provider failure from model failure, keeps `n/a` results honest, and preserves reasons,
coverage, fingerprints, signatures, diffs, trials, and exports.

## What the demo proves

1. Guard accepts a real ClawHub URL and returns `review` when no golden cases exist.
2. Certification produces a signed, fingerprint-bound certificate and badge without an
   API key.
3. Arena runs the same executor without and with a skill and exports measured uplift.
4. Improve shows measure → propose → re-measure → gate; rejected rewrites never mutate.
5. Models distinguishes real LLM catalogs, deterministic fixtures, key sources, and
   structured provider errors without displaying secrets.
6. A thin stdio MCP adapter lets Codex run the same evidence flows without GUI-specific
   instructions or a second scoring implementation.

## How Codex was used

Codex was the primary implementation environment. The repository was rebuilt from
`docs/SPEC.md` in small milestone sessions: core contracts, provider adapters, CLI and
HTTP surfaces, the no-framework GUI, deterministic fixtures, regression tests, demo
scripts, and documentation. Product decisions remained human-directed: the unit under
test is the skill; deterministic checks are authoritative; provider failures are not
zero scores; Improve is dry-run by default; and adversarial cases require review before
they become frozen regressions.

Every behavior increment was tested and committed separately. `docs/POSTMORTEMS.md`
records observed failures and the guardrails carried into subsequent work.

## How GPT-5.6 is used in the product

GPT-5.6 has two roles. Codex with GPT-5.6 helped build the repository, and
`openai:gpt-5.6-sol` is a selectable product tier for certification, Arena execution,
Improve authorship, and independent gates. GPT-5.6 may generate an output, rewrite, or
trap candidate; it never awards itself a passing score. The declared deterministic check
does that.

## Existing-project disclosure

The product specification was distilled from a two-month predecessor experiment. Work
submitted for Build Week is the clawreinforce rebuild and the dated extensions visible
in this repository's commit history and Codex sessions. The predecessor's measured
instruct-versus-fewshot result informed the Improve gate design; predecessor code is not
presented as newly generated Build Week work.

## Judge quick test — zero keys

Requirements: Python 3.11+ on Windows, macOS, or Linux. No Node runtime is required.

```console
python -m venv .venv
python -m pip install -e .
python -m clawreinforce certify examples/incident-triage-skill --tier fixture:reference
python -m clawreinforce bench examples/incident-triage-task examples/incident-triage-skill --tier fixture:reference --trials 2
python -m clawreinforce serve --project . --host 127.0.0.1 --port 8788
```

Expected signals: certification `coverage: 10/10`, `pass_rate: 1.0`; Arena `without_skill: 0.0`,
`with_skill: 1.0`, `uplift: 1.0`; GUI at `http://127.0.0.1:8788`.

For the scripted path and narration, use `docs/DEMO.md`. Only optional real-provider
calls require a provider key.

Agent-driven testing instructions are in `docs/AGENT_QUICKSTART.md`.

## Honest current boundaries

- SkillsBench tasks with official container verifiers can be fetched but are `ungraded`
  in the lightweight runner; the reason remains visible.
- `agent` checks are single-shot artifact grading, not an iterative tool loop.
- Deterministic fixtures prove installation and scoring offline; they are not LLMs.
- Real-model cost is shown only when a provider reports usage or pricing is known.

## Final submission checklist

- [ ] Repository link works from a signed-out browser or both judge accounts have access.
- [ ] A deliberate public license is present, or the repository is private and shared.
- [ ] Video is public/unlisted, audible, under three minutes, and works signed out.
- [ ] `/feedback` Session ID is included.
- [ ] README install, supported platforms, and zero-key judge path are current.
- [ ] Fresh-clone script and full tests pass at the submitted commit.
- [ ] Video numbers match saved run output and no secret is visible.
- [ ] Submission text and video are in English.
