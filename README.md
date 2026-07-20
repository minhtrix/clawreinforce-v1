# clawreinforce

> No agent should run a skill nobody verified.

clawreinforce is CI for agent skills. It fetches untrusted skill bundles, scans their instructions, certifies declared behavior with deterministic checks, compares model performance with and without a skill, and emits fingerprint-bound trust evidence instead of asking an LLM to judge another LLM.

## 60-second quickstart — zero API keys

The built-in fixture provider is deterministic and requires no account, network access, or secret:

```console
$ python -m pip install -e .
$ clawreinforce certify examples/hello-skill --tier fixture:echo
$ clawreinforce guard examples/hello-skill --tier fixture:echo
$ clawreinforce bench examples/uppercase-task examples/uppercase-skill --tier fixture:upper-if-skilled --trials 2
```

Expected signals in the JSON output:

```text
certify  -> status: completed, pass_rate: 1.0, signed certificate_path
guard    -> verdict: install
bench    -> without_skill: 0.0, with_skill: 1.0, uplift: 1.0, coverage: 2/2
```

Run the tests with `python -m pip install -e ".[dev]"` followed by `python -m pytest`.

## Improve a failing skill

Improve is dry-run by default: the selected tier grades every golden case, proposes at most the requested number of rewrites, and prints the accepted unified diff. Add `--apply` only when the gated body should replace the current instructions.

The GUI separates one **author model** from any number of **gate models**. The author only proposes; every gate model re-runs every golden case, and a previously green model × case regression blocks the candidate. Improve reports one completion per pair and points to Arena trials when statistical confidence is required.

The same tab includes an adversarial **Trap Lab**. The selected author becomes the breaker, every selected gate model executes each safe deterministic candidate, and the result shows the expected check, actual output, and failure reason per model. Breaker rationales remain explicitly untrusted hypotheses. Nothing is persisted by default: only individually selected, human-reviewed failures can be appended to `.clawreinforce/regressions.jsonl`; frozen traps become certification cases and change the skill fingerprint.

```console
$ clawreinforce improve examples/improvable-uppercase-skill --tier fixture:upper-if-skilled --strategy fewshot --max-rewrites 3
```

`instruct` requests a complete rule rewrite. `fewshot` requests outputs for failing cases and inserts only examples that pass those cases' real deterministic checks. Every candidate must turn its target green without regressing any previous pass.

## GUI

```console
$ clawreinforce serve --project . --host 127.0.0.1 --port 8788
```

Open [http://127.0.0.1:8788](http://127.0.0.1:8788). The HTTP-only web client exposes four product areas: Verify, Improve, Arena, and Models. Configured remote providers are discovered once on load, so their real LLMs appear as provider-grouped click targets without typing; bulk-select handles large catalogs. Deterministic fixtures remain available in a separate **not LLMs** group. Verify and Arena accept multiple LLMs, while Improve separates one Author / Breaker from any number of Gate models.

Long Arena runs stream raw trials over Server-Sent Events, then aggregate them per LLM into **without skill → with skill → uplift** lines. The summary counts improved, regressed, and fully solving models and reports Pass@1, Pass@k, Pass^k, a Wilson 95% interval, tokens, and cost when providers expose them.

## How Codex was used

This repository was built in milestone-focused Codex sessions from the recovered master specification in [docs/SPEC.md](docs/SPEC.md). Codex translated that spec into the core/adapter/web architecture, implemented the CLI and HTTP surfaces, wrote the deterministic fixtures and regression tests, integrated remote skill and task sources, and kept each behavior change behind a green test increment and an evidence-bearing Git commit.

## How GPT-5.6 is used

GPT-5.6 has two roles. First, Codex with GPT-5.6 built the repository from `docs/SPEC.md`. Second, GPT-5.6 runs inside the product: `openai:gpt-5.6-sol` is the default certification tier and can also be selected as the Arena executor for same-model comparisons with and without a skill. The deterministic check, not GPT-5.6, decides whether an output passes.

## Positioning vs ClawBench

ClawBench (github.com/openclaw/shellbench) benchmarks **models** as OpenClaw agents on a
fixed curated task suite (completion/trajectory/behavior/reliability, pass^k, deterministic
verification, advisory-only LLM judge). We share its verification philosophy — verify the
work, never trust the transcript, deterministic official scores — and cite it respectfully.
The difference is the unit: **ClawBench ranks models; this tool certifies and improves
SKILLS.** It measures a skill's uplift (same model WITH vs WITHOUT the skill), gates
self-rewrites, and issues fingerprint-bound signed certificates — and it changes the
artifact, not just scores it. One sentence for the README: "ClawBench tells you which model to run. clawreinforce tells you which skills to trust — and makes them better. Agents need both."

## Architecture and invariants

1. `core/` owns pure domain logic and imports no HTTP or web code.
2. CLI and HTTP adapters map the same core functions; the web client uses HTTP only.
3. Skill fingerprints bind certificates and reports to the exact inspected bytes.
4. Deterministic checks are the only scoring authority; there is no LLM-as-judge score.
5. Executable checks run in temporary subprocesses with time and output limits.
6. Provider failures remain unavailable coverage and are never converted into zero scores.
7. JSONL ledgers are append-only sources of truth; GUI reports are projections.
8. `agent` checks are single-shot task-artifact grading, with no iterative tool loop yet.
9. Provider secrets come from environment variables first or ignored local configuration.
10. Files stay focused and near 300 lines; tests ship in the same commit as behavior.

## Sources, providers, and current boundary

Verify accepts local skill paths, GitHub tree URLs, ClawHub slugs, and canonical ClawHub page URLs. Arena accepts local tasks, GitHub task folders, and `skillsbench.ai/tasks/<slug>` links. SkillsBench prompts and metadata import cleanly, but their official container verifier is not part of this lightweight runner, so those rows are honestly marked `ungraded`.

Provider keys can be set through environment variables or ignored `.clawreinforce/providers.json`. The provider hub supports OpenAI, Anthropic, Ollama, Ollama Cloud, and configurable OpenAI-compatible endpoints. Use `clawreinforce models --project . --discover <provider>` to inspect a provider's current catalog without exposing its key.

## Predecessor

The Build Week specification was distilled from a two-month predecessor project. Its measured instruct-vs-fewshot A/B result informs the Improve gates: few-shot examples are most effective when the same model mines and executes them, while instruct-style rules transfer more reliably across executor models.
