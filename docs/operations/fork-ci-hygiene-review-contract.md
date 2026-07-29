# Fork CI Hygiene — Review Contract

> **Companion to** `fork-ci-hygiene-spec.md`. That file says what the change
> intends; this file says how a reviewer decides whether it succeeded.

## How to use this contract

The numbered clauses **C1–C13** below are the complete, finite acceptance set.
Every one of them is decidable from the **review packet alone** — this contract
plus the complete diff and the commit history from the base — with no network
access, no CI run, and no code execution. A reviewer who can read
`git log --patch <base>..<head>` can return a verdict on every numbered clause.

There is nothing else to check. If a clause holds, it holds; if the packet does
not settle a clause, that clause **fails** rather than being resolved by
judgment or by trusting a claim made elsewhere.

Anything that needs a process to run, a CI service to answer, or a remote to be
mutated is **out of the numbered set** and appears at the bottom as unnumbered
orchestrator gates. Those are not this change's to certify.

**Base:** `76b0ea5118ca11373e49234cd8bdd608848e423f`.

---

## Numbered clauses (packet-provable)

### Scope

- **C1 — Changed-path closure.** The complete diff from base to head touches
  only:
  1. `docs/operations/fork-ci-hygiene-spec.md` (added),
  2. `docs/operations/fork-ci-hygiene-review-contract.md` (added),
  3. `tests/tools/test_tts_xai_speech_tags.py` (modified),
  4. exactly one added file under `contributors/emails/`.

  Any fifth path fails C1.

- **C2 — No production or workflow edits.** No file under `tools/`, `agent/`,
  `gateway/`, `hermes*`, `scripts/`, `.github/`, `plugins/`, `web/`, `apps/`, or
  any dependency manifest (`pyproject.toml`, `uv.lock`, `package.json`,
  `package-lock.json`, `flake.*`) appears in the diff.

- **C3 — No environment or credential surface.** The diff introduces no `.env`
  file, no `HERMES_*` environment variable, no secret-shaped literal (API key,
  token, bearer, password), and no change to any workflow `permissions:` block.

### Defect A — test doubles

- **C4 — Exact edit shape.** Every hunk in `tests/tools/test_tts_xai_speech_tags.py`
  changes a line of the form

  ```python
  def fake_post(url, headers, json, timeout):
  ```

  to

  ```python
  def fake_post(url, headers, json, timeout, stream=False):
  ```

  and nothing else. No added, removed, or reworded `assert`; no changed
  monkeypatch target; no changed fixture, import, docstring, or test name.

- **C5 — Count.** Exactly four such hunks appear — one per double that lacked
  the parameter at base. The diff shows four `+`/`-` line pairs in this file and
  no other net line change.

- **C6 — Post-state completeness.** At head, no `def fake_post(...)` in that
  file omits a `stream` parameter. (Provable from the base file plus the diff:
  base had fourteen doubles, ten already carrying `stream=False`; the four
  edited ones close the set.)

- **C7 — Signature parity with the unchanged production call.** The single
  production call site — `requests.post(url, headers=..., json=..., timeout=60,
  stream=True)` in `_generate_xai_tts()` — is **absent from the diff** (implied
  by C2), so its keyword set is fixed at the base value. Each edited double
  accepts every keyword that call passes. Parity is achieved by moving the
  double toward the production call, never the reverse.

- **C8 — No assertion weakening.** For each of the four affected tests, the set
  of assertions at head is identical to the set at base. A reviewer confirms
  this by observing that no `assert` line appears with a `+` or `-` marker
  anywhere in the diff.

### Defect B — contributor mapping

- **C9 — Exactly one mapping, correctly shaped.** The diff adds exactly one file
  under `contributors/emails/`. Its name contains no path separator and is a
  bare `<local>@<domain>` email. Its first non-comment line is a single GitHub
  login matching `^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$` (the
  `_LOGIN_RE` enforced by `scripts/add_contributor.py`). Any further lines begin
  with `#`.

- **C10 — The mapped email is the one CI rejects.** The added file's name is
  byte-identical to an author email produced by
  `git log --format='%ae' --no-merges <base>..<head>` over the packet's own
  history, and that email matches none of the workflow's skip cases (it is not a
  `*@users.noreply.github.com` id+login address, not a bot address, not a
  maintainer address).

- **C11 — Not a duplicate, not a reassignment.** At base, no file of that name
  exists under `contributors/emails/` and the email appears as no quoted key in
  `scripts/release.py`. The mapping therefore adds an identity rather than
  silently reassigning one. (Both halves are checkable against the base tree in
  the packet.)

- **C12 — Legacy map untouched.** `scripts/release.py` is absent from the diff
  (implied by C2), so `AUTHOR_MAP` / `LEGACY_AUTHOR_MAP` remain frozen, as
  `contributors/README.md` requires. The workflow predicate the change satisfies
  is the directory branch (`[ -f "contributors/emails/${email}" ]`), not a
  weakening of the check itself — `.github/workflows/contributor-check.yml` is
  likewise absent from the diff.

### Commit custody

- **C13 — Contract-first, conventional commits.** The history from base to head
  shows the two documents committed **first**, in a commit that contains those
  two files and nothing else, before any commit touching the test file or the
  mapping. Every commit subject follows the repository's conventional-commit
  form (`fix(...)`, `docs(...)`, `chore(...)`, `test(...)`), and no commit
  reverts or amends a document introduced by the first commit.

---

## Orchestrator gates (NOT part of the numbered set)

These are real acceptance conditions for the overall effort, but they are **not
provable from the packet** and are not claimed by this change. Custody sits with
the orchestrating parent, which owns every remote action and any independent
review. Each is listed with who settles it and what evidence settles it.

**Runtime custody — did the tests actually run and go green?**
Settled by executing the suite, not by reading the diff. Evidence is the
recorded RED-before / GREEN-after invocation and its output in the lane worklog.
A reviewer may read that record as reporting; the numbered clauses above do not
depend on it, and a passing local run does not substitute for any clause.

**CI custody — did the blocked checks turn green on the PR?**
Settled only by the hosting service running `tests.yml` and
`contributor-check.yml` against the PR head, on the PR's real merge base
(the local base and the PR merge base can differ). Nothing in this packet can
demonstrate a CI outcome. Note also that the contributor job re-derives the
email set from the PR range, so its verdict is a function of the PR's commits,
not of this diff alone.

**PR custody — pushing, labelling, commenting, merging.**
Out of scope entirely. This change is prepared locally: no push, no PR mutation,
no merge, no label, no force-push, no install, no service enable/restart, no
credential change. The parent performs and owns all of it, together with any
independent second review.

**Deploy/live custody.**
Not applicable — the change alters test doubles and repository metadata only.
`merged ≠ deployed ≠ live`; none of those states is claimed here.
