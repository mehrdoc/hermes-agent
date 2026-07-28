# Credential-bearing URL log scrubbing specification

Date: 2026-07-28

## Incident evidence

Two nonstandard Hermes logs bypass the ordinary `RedactingFormatter`: stdio MCP child stderr is inherited directly into `mcp-stderr.log`, and the detached shutdown diagnostic inherits a file descriptor while recording process listings. On hal-dev, bounded name-only counting found 574 `apiKey` occurrences in `mcp-stderr.log` and 22 in `gateway-shutdown-diag.log`. No example line or value is admissible evidence.

## Required behavior

1. Add a narrow forced helper in `agent.redact` that redacts sensitive query parameter values in full and relative request URLs regardless of the global tool-output URL-redaction policy. It must not enable blanket URL redaction in normal agent/tool content.
2. Stdio MCP stderr must pass through an in-process pipe/reader before append. Every line is force-scrubbed before `mcp-stderr.log` write. The object given to the MCP subprocess must retain a real writable file descriptor.
3. If pipe setup or redaction fails, fail closed to devnull or a fixed marker; never fall back to raw stderr/log output.
4. Shutdown diagnostics must collect bounded output in their detached child and force-scrub it before appending to `gateway-shutdown-diag.log`. Preserve fire-and-forget, POSIX-only, timeout-bounded behavior and PID return.
5. Existing logs are not rewritten. This PR prevents new URL credential values at write time.
6. Add fixture-only regressions using fake values. Prove old direct-write behavior would retain the fixture, then prove both write paths retain URL structure/ordinary params while removing the sensitive value. Never inspect a real log line or token value.

## Scope

Limit production changes to `agent/redact.py`, `tools/mcp_tool.py`, and `gateway/shutdown_forensics.py`, plus narrow tests and these contract documents. No install, restart, deploy, credential access, live-log rewrite, or unrelated logging refactor.
