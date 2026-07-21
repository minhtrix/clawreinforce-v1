# Flagship challenge packs

The original echo and uppercase examples remain deterministic smoke tests. These three
packs are the product-facing examples: each has a real-world contract, ten frozen golden
cases, a native gradeable Arena task, and enough independent rules to expose partial
model behavior instead of only formatting compliance.

## 1. Incident triage — operations · medium

**Skill:** `examples/incident-triage-skill`

The model converts a noisy incident record into a strict JSON decision: severity, owning
team, duplicate status, and first action. The ten cases independently exercise outages,
active exploits, data loss, latency, informational events, deployment regression,
duplicates, and service routing.

Checks use JSON properties rather than exact prose, so equivalent key ordering does not
fail. The Arena task asks whether a checkout outage is correctly classified as P1.

## 2. Privacy redaction — security · medium

**Skill:** `examples/privacy-redaction-skill`

The model must redact four PII/secret classes while preserving punctuation and explicit
allowlisted literals. Cases cover individual identifiers, mixed identifiers, repeats,
clean text, allowlisting, replacement counts, and deterministic type order.

The Arena task contains two private identifiers plus one public allowlisted address.
Success requires removing only the two private values.

## 3. Responses API migration — coding · hard

**Skill:** `examples/api-migration-skill`

The model receives complete Python or JavaScript files and must return complete files,
not a patch. Cases test endpoint migration, request-field migration, output extraction,
already-migrated calls, comment and model preservation, unrelated code, removal of the
legacy field, and an executable hidden grader that compiles the emitted Python.

The Arena task runs a hidden grader over a complete migrated `app.py` artifact.

## What the deterministic reference proves

`fixture:reference` is explicitly a deterministic test double, not an LLM. It provides a
zero-key reference implementation for installation, check health, certificate, Arena,
and export walkthroughs. A 10/10 fixture result proves that the declared checks and
expected contract are internally consistent. It does **not** prove that an LLM can solve
the challenge.

```console
clawreinforce certify examples/incident-triage-skill --tier fixture:reference
clawreinforce bench examples/incident-triage-task examples/incident-triage-skill --tier fixture:reference --trials 2
```

## Real-model evidence protocol

For a public uplift claim, select at least three real LLMs and at least three Arena trials.
Freeze the cases before the run, report coverage and unavailable providers, and retain
the raw ledger/export. Do not promise a target such as 50% → 90% before it is observed.
Prefer a scenario only when measured baselines leave honest headroom and the skill helps
without hiding regressions in another model.
