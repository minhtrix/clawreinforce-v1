---
name: privacy-redaction
description: Redact emails, US phone numbers, SSNs, and API keys while preserving explicit allowlisted literals.
kind: flagship
category: security
difficulty: medium
---

<!-- CLAWREINFORCE_SCENARIO: privacy-redaction -->

You receive one JSON object with `text` and an optional `allowlist`. Return only a valid
JSON object with `redacted_text`, `redaction_count`, and `types`.

Replace API keys matching `sk-` plus at least 16 alphanumeric characters with
`[API_KEY]`; email addresses with `[EMAIL]`; US SSNs in `000-00-0000` form with `[SSN]`;
and common ten-digit US telephone forms, optionally prefixed by `+1`, with `[PHONE]`.
Never redact an exact literal listed in `allowlist`. Count every replacement, list each
encountered type once in the processing order API_KEY, EMAIL, SSN, PHONE, and preserve
all other text and punctuation exactly.
