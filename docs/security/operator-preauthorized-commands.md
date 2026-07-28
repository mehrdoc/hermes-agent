# Operator-Preauthorized Commands (`approvals.preauthorized`)

Normative specification for the operator-preauthorized command-shape allowlist
in `~/.hermes/config.yaml`, consulted by `tools/approval.py`.

Keywords **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used in the
RFC 2119 sense.

## 1. Problem

An operator ratifies an operation in chat ("yes, restart the gateway"), the
agent goes to run it, and the terminal guard raises a *second* approval prompt
for the same operation on a surface where nobody can answer it — a gateway
session with no notify callback registered, a cron run, or simply an operator
who has already given the answer once. The operation dies at the guard.

The existing escape hatches are all wrong-shaped for this:

| Mechanism | Why it does not fit |
| --- | --- |
| `--yolo` / `/yolo` / `approvals.mode: off` | Blanket. Disables the guard for *every* command, not the one that was ratified. |
| `command_allowlist` (`[a]lways` at the prompt) | Glob-matched against the raw command **string** (`fnmatch` with `*`/`?`/`[…]`), and only reachable by answering a prompt — which is exactly the prompt that could not be answered. |
| `approvals.deny` | The inverse direction (unconditional block). |

`approvals.preauthorized` is the narrow, auditable, argv-shaped counterpart:
the operator writes down, ahead of time and in the config file, the exact
command shapes they have already ratified.

## 2. Scope of authority — what preauthorization CAN and CANNOT do

Preauthorization satisfies **exactly one** requirement: the *interactive
human-approval prompt raised by dangerous-pattern detection*. It is a
statement that a human has already answered that prompt, out of band.

It **MUST NOT** be able to satisfy anything else. Specifically, a
preauthorized entry **MUST NOT**:

1. **Bypass the hardline floor.** `detect_hardline_command()` — `rm -rf /`,
   `mkfs`, `dd` to a raw device, `shutdown`/`reboot`, fork bombs, `kill -1`,
   parser-limit and malformed-payload blocks — is unconditional. Not yolo, not
   `mode: off`, not cron approve mode, not preauthorization.
2. **Bypass the sudo-stdin guard.** `_check_sudo_stdin_guard()` blocks
   `sudo -S` password guessing unconditionally.
3. **Bypass user deny rules.** `approvals.deny` is the operator saying "never,
   even under yolo". A `deny` match **MUST** win over a `preauthorized` match;
   see §6.
4. **Bypass protected machine boundaries.** The container fast-path
   (`_should_skip_container_guards`) and the `has_host_access` demotion are
   evaluated before preauthorization and are unaffected by it.
5. **Bypass content-level security scanning (secret safety).** Tirith findings
   (`block` / `warn` — homograph URLs, pipe-to-interpreter, terminal injection,
   secret exfiltration shapes) are raised on the *content* of a command, not
   its shape. A preauthorized shape says nothing about the content that happens
   to be flowing through it, so tirith findings **MUST** still raise the
   approval prompt. See §6 step 9.
6. **Grant any authority beyond the command it matches.** No prefix authority,
   no wildcard authority, no "this argv plus more arguments". Exact argv
   equality only (§4).

Out of scope by construction, because they are not command-shaped:

- `request_tool_approval()` (plugin `pre_tool_call` escalations) — keyed on a
  synthetic tool label, not argv.
- `check_execute_code_guard()` — inspects source code, which has no argv.
- File-write deny lists (`tools/file_operations.py`) — path-shaped.

## 3. Configuration

```yaml
approvals:
  preauthorized:
    # String form — parsed into argv by the shared parser (§4.1).
    - systemctl restart hermes-gateway
    - docker compose -f /srv/hermes/docker-compose.yml up -d
    # List form — literal argv, no parsing, no ambiguity. Preferred when
    # an argument would otherwise need quoting.
    - [git, push, origin, main]
```

Rules:

- The key is `approvals.preauthorized`. Default is `[]` (in `DEFAULT_CONFIG`).
- It is **behavioral configuration, not a credential**, so it lives in
  `config.yaml`. There **MUST NOT** be a `HERMES_*` env var counterpart
  (AGENTS.md: "New `HERMES_*` env vars for non-secret config" is a reject).
- A missing key, `null`, `[]`, a non-list value, or a list of only invalid
  entries **MUST** authorize nothing. Absence is never authority.
- Entries are **never** written by Hermes. Unlike `command_allowlist`, no
  prompt answer, no `[a]lways`, and no agent action adds an entry. It is an
  operator-authored file section, which is what makes it auditable.

## 4. Matching — exact, anchored, argv-shaped

### 4.1 The eligible command shape

Both the incoming command and each string-form config entry are reduced to an
argv list by the *same* parser. A command is **preauth-eligible** only if it is
a single simple command with no shell semantics at all:

1. It **MUST** be non-empty after stripping.
2. It **MUST NOT** exceed the detector's parser limits
   (`_command_parser_limit_exceeded`).
3. Every character **MUST** be drawn from the safe set
   `A–Z a–z 0–9 _ . / : @ % + = , -` plus space and tab. This excludes, by
   construction: `; & | < > ( ) { } $ \` \ ' " * ? [ ] ~ ! # ` and newline —
   i.e. every separator, redirect, substitution, expansion, glob, quote, and
   escape. A command containing any of them is **not** preauth-eligible.
4. Tokenization is `shlex` in POSIX mode. Every resulting token **MUST**
   match `_SIMPLE_SHELL_LITERAL_RE` (`^[A-Za-z0-9_./:@%+=,-]+$`).
5. Any parse failure, empty token list, or token failing (4) **MUST** fail
   closed — no match.

Rationale for the character allowlist rather than a metacharacter blocklist:
the guard's job is to guarantee that the argv we compared is the argv the shell
will actually execute. Anything that expands, substitutes, globs, redirects, or
separates at execution time breaks that guarantee. A positive allowlist is
auditable by inspection; a blocklist is a race against shell syntax. Rejecting
is always safe — the command simply falls through to the normal approval
prompt.

Consequence, and it is intentional: `rm -rf ~/.cache/foo` is not eligible
(tilde expansion); write the absolute path. `a && b` is not eligible; that is
two operations and each is preauthorized separately or not at all.

### 4.2 Entry validation

A config entry is **valid** only if:

- **String form**: the string is preauth-eligible per §4.1, yielding argv.
- **List form**: a non-empty list whose every element is a `str` matching
  `_SIMPLE_SHELL_LITERAL_RE`. Used directly as argv, no parsing.
- And, for both forms, the entry's own command text **MUST NOT** match
  `detect_hardline_command()`. An operator cannot preauthorize a hardline
  command; such an entry is rejected outright. (Defense in depth: §6 ordering
  already blocks such a command before preauthorization is consulted. This
  rule makes the config itself refuse to *look* like it grants that authority.)

An invalid entry **MUST** be skipped — logged once at `WARNING` with the
offending entry, never raising, never authorizing. A single bad entry
**MUST NOT** disable the valid entries around it, and **MUST NOT** authorize
anything.

### 4.3 The comparison

`argv == entry_argv` — element-by-element equality, same length,
case-**sensitive** (POSIX commands and paths are case-sensitive; the
case-insensitive matching used by `approvals.deny` is correct for a *blocking*
rule and wrong for a *granting* one).

There is **no** substring matching, **no** prefix matching, **no** `fnmatch`,
**no** regex, and **no** normalization/deobfuscation-variant expansion. The
deobfuscation variant machinery exists to stop an attacker *hiding* a command
from a blocking detector; feeding variants into a *granting* check would let a
crafted spelling reach a grant it was not written for. Grants are matched on
one canonical form only.

### 4.4 Reporting

On a match, the module returns the matched entry in display form (the original
string, or the shell-joined argv for list form) so the log line and any
downstream surface can name exactly which config line granted the operation.

## 5. Failure modes — all fail closed

| Condition | Behavior |
| --- | --- |
| Key absent / `null` / `[]` | No authorization. |
| `preauthorized` is not a list (e.g. a bare string, a dict) | No authorization; `WARNING`. |
| Entry is not a string or list of strings | Entry skipped; `WARNING`. |
| Entry contains a shell metacharacter | Entry skipped; `WARNING`. |
| Entry is itself hardline | Entry skipped; `WARNING`. |
| Config load raises | No authorization (caught, `WARNING`). |
| Command not preauth-eligible (§4.1) | No match; normal approval flow. |
| `shlex` raises `ValueError` (unbalanced quoting) | No match. |
| argv differs in any element or length | No match. |

"No match" is never an error to the caller — it means the command proceeds
into the ordinary approval flow it would have taken without the feature.

## 6. Decision ordering (normative)

`tools/approval.py` remains the single decision point. The preauthorization
check occupies exactly one position in each entry point's existing ladder, and
that position is **after every unconditional block** and **before the
human-approval prompt for dangerous-pattern findings**.

For `check_all_command_guards()`:

1. Container fast-path (`_should_skip_container_guards`) → allow.
2. Hardline floor → **BLOCK** (unconditional).
3. Sudo-stdin guard → **BLOCK** (unconditional).
4. `approvals.deny` → **BLOCK** (unconditional; beats preauthorization).
5. yolo / `mode: off` → allow.
6. `command_allowlist` (permanent, string/glob) → allow.
7. Non-interactive, non-gateway, non-ask → existing cron / fall-through policy,
   unchanged by this feature.
8. Tirith content scan → findings gathered.
9. Warning synthesis — **preauthorization is consulted here**. A preauth match
   suppresses **only** the dangerous-pattern warning. A tirith `block`/`warn`
   finding still becomes a warning and still raises the prompt.
10. Smart approval (`mode: smart`), then the human prompt, for whatever
    warnings remain.

For `check_dangerous_command()` (no tirith stage): the same ladder, with the
preauthorization check placed after dangerous-pattern detection and before
`_run_approval_gate()`.

Two invariants follow, and both **MUST** be regression-tested:

- **A hardline / sudo-stdin / deny command that is also listed in
  `preauthorized` is still blocked**, and the returned result carries the
  blocking reason (`hardline` / `user_deny`), not an approval.
- **A preauthorized command with a tirith finding still prompts.**

## 7. Observability

A successful preauthorization **MUST** emit a `logger.info` line naming the
matched entry and the dangerous-pattern description it satisfied, e.g.:

```
Preauthorized command allowed (entry: 'systemctl restart hermes-gateway';
would have prompted for: service restart)
```

A grant that leaves no trace is not auditable. Invalid entries log at
`WARNING` (§4.2).

## 8. Operator guidance

- Prefer list form for anything with more than three tokens; it is unambiguous
  and diffs cleanly.
- Write absolute paths. `~`, `$HOME`, and globs are not eligible (§4.1).
- Preauthorize the narrowest shape that does the job. `docker compose up -d` is
  a shape; `docker` is not expressible (there is no prefix authority) and that
  is the point.
- Reach for `approvals.deny` for the inverse, and for `command_allowlist` when
  you genuinely want glob breadth and are answering a live prompt to get it.
- Review the block the way you would review `authorized_keys`: every line is a
  standing grant that survives restarts.

## 9. Relationship to existing config keys

| Key | Direction | Matching | Written by |
| --- | --- | --- | --- |
| `approvals.deny` | Block, unconditional | `fnmatch` glob, case-insensitive, over deobfuscation variants | Operator |
| `command_allowlist` | Allow (approval prompt only) | Exact string or `fnmatch` glob, case-sensitive, rejects compound commands | Prompt `[a]lways` + operator |
| `approvals.preauthorized` | Allow (approval prompt only) | Exact argv equality, case-sensitive, single simple command only | Operator only |

## 10. References

- `tools/approval.py` — detection, ordering, and the gate.
- `docs/security/operator-preauthorized-commands-review-contract.md` — the
  ordered review contract for this change.
- `SECURITY.md` §2 — trust model; the terminal backend as execution boundary.
- `AGENTS.md` — config-vs-env policy, E2E-against-real-`HERMES_HOME` policy.
