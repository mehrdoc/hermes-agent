# Recursive sensitive-key JSON redaction review contract

The fresh reviewer receives only this contract/specification and the complete base-to-head history/diff. Missing diff evidence is FAIL.

1. **Recursive coverage** — valid JSON dict/list structures are traversed to arbitrary depth and any exact case-insensitive sensitive key has its complete value replaced.
2. **No false positives or material retention** — matched values become fixed `***`; non-sensitive siblings and near-miss key names remain intact.
3. **Compatibility** — secret-free JSON remains byte-for-byte unchanged; direct environment lookup strings, `code_file`, invalid JSON, and embedded-text behavior preserve existing contracts.
4. **Regression** — fixture tests prove the old KEL-877-shaped nested `token` object would survive flat matching and now cannot survive; dict/list depth and negative branches are covered without real credential data.
5. **Hygiene** — diff is limited to spec/contract, `agent/redact.py`, and narrow tests; no credential/log access, runtime artifact, install/deploy action, or unrelated redactor change.

External orchestrator gate, outside the packet-only verdict: the PR body must state that live deployment is a separate operator decision.

Reviewer must state fresh Codex session class, exact SHA, packet filename, one ordered PASS/FAIL per item, blockers, and final `VERDICT: PASS|FAIL`.
