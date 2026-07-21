---
name: incident-triage
description: Convert noisy incident signals into a deterministic severity, owner, duplicate flag, and first action.
kind: flagship
category: operations
difficulty: medium
---

<!-- CLAWREINFORCE_SCENARIO: incident-triage -->

You triage production incidents from one input JSON object. Return only one valid JSON
object with exactly these keys: `incident_id`, `severity`, `owner`, `duplicate`, and
`action`.

Severity rules, evaluated in order:

1. `P1` for an outage, active exploit, data loss, or customer impact of at least 50%.
2. `P2` for degradation, latency, elevated 5xx, a regression, or any smaller customer impact.
3. `P3` otherwise.

Route active exploits, credentials, or malware to `security`; authentication, login, or
identity issues to `identity`; payments, billing, or checkout issues to `payments`; and
everything else to `platform`. Set `duplicate` to true when `repeated_count` is at least
2. For security incidents, isolate and page security. For a recent deployment, roll it
back and page the service owner. For other P1 incidents, page the owner and start an
incident bridge. Otherwise investigate with the owner. Never invent missing evidence.
