---
name: openai-responses-migration
description: Migrate simple Chat Completions calls to the Responses API while preserving complete files and unrelated code.
kind: flagship
category: coding
difficulty: hard
---

<!-- CLAWREINFORCE_SCENARIO: api-migration -->

You receive one JSON object whose `files` property maps file paths to complete source
text. Return only one JSON object mapping the same paths to complete migrated source.

For straightforward Python or JavaScript OpenAI calls, replace
`chat.completions.create` with `responses.create`, rename the request field `messages` to
`input`, and replace `.choices[0].message.content` reads with `.output_text`. Preserve
model names, other parameters, comments, imports, control flow, unrelated files, and
secret literals exactly. Leave already migrated calls unchanged. Never return a patch,
Markdown fence, explanation, omitted section, or new file.
