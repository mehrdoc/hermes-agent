# Recursive sensitive-key JSON redaction specification

Date: 2026-07-28

## Problem

`agent.redact.redact_sensitive_text()` currently masks JSON only when a sensitive key is followed directly by a quoted string. A valid JSON document can therefore retain an opaque secret when a sensitive key appears at a deeper dict/list level or owns a structured value. The KEL-877 class is a credential object nested beneath a `token` key; its fixture value has no vendor prefix, so regex prefix passes do not save it.

## Required behavior

1. For a complete valid JSON document in a normal log/text context, recursively traverse dictionaries and lists at arbitrary depth.
2. Match `_SENSITIVE_BODY_KEYS` case-insensitively by exact key name. When matched, replace the complete value — scalar, dict, or list — with the fixed string `***`; do not preserve any secret bytes.
3. Preserve all non-sensitive siblings and list structure. Keys such as `token_count`, `session_id`, and `secretary` must remain untouched.
4. If no recursive replacement occurs, return the original text byte-for-byte. Do not reformat ordinary JSON.
5. Preserve the existing direct-string environment-lookup exception (`os.getenv(...)` / `os.environ...`) and the `code_file` bypass. Invalid or embedded JSON continues through existing regex behavior.
6. Add fixture-only regressions that are RED on the old implementation, including the KEL-877-shaped `token` object nested through dict/list containers. Never use or inspect a real token file/value.

## Scope and deployment boundary

Limit the diff to `agent/redact.py`, narrow redaction tests, and these documents. No log, credential, install, restart, or deployment access. This fork PR does not deploy itself to the live Hermes installation; deploying the fork is a separate operator decision.
