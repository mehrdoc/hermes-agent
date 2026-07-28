# Credential-bearing URL log scrubbing review contract

The fresh reviewer receives only this contract/specification and the complete base-to-head history/diff. Missing diff evidence is FAIL.

1. **Forced narrow scrubber** — sensitive query values in full and relative URLs are masked by an explicit forced helper, while normal `redact_sensitive_text` URL behavior remains unchanged.
2. **MCP write boundary** — MCP child stderr reaches `mcp-stderr.log` only through a real-fd pipe reader that scrubs before append; setup/redaction failure cannot write raw data.
3. **Shutdown write boundary** — detached shutdown diagnostics remain timeout-bounded and append only bounded scrubbed output; failure cannot append raw data.
4. **Regression** — fixture tests prove sensitive values are absent, URL/non-sensitive context remains useful, the MCP sink has a real fd, and current shutdown spawning behavior remains intact.
5. **Hygiene** — diff is limited to the spec/contract, three named production files, and narrow tests; no real secret/log samples, runtime artifacts, install/deploy action, or global feature-breaking URL redaction.

Reviewer must state fresh Codex session class, exact SHA, packet filename, one ordered PASS/FAIL per item, blockers, and final `VERDICT: PASS|FAIL`.
