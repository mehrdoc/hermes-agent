# Fork CI Hygiene — Specification

> **Scope:** two CI failures that block a fork PR for reasons unrelated to that
> PR's subject matter. This document defines the intended change *before* it is
> written. The companion file `fork-ci-hygiene-review-contract.md` defines how
> the finished change is judged.

**Base:** `76b0ea5118ca11373e49234cd8bdd608848e423f`
(`origin/review-base/upstream-76b0ea5`).

---

## 1. Why this exists

A fork PR carries two red CI checks that have nothing to do with the change it
proposes:

- **Defect A — stale test doubles in the xAI TTS suite.** Four `fake_post`
  doubles predate a production change and no longer accept the keyword the real
  call passes, so the doubles raise `TypeError` before any assertion runs.
- **Defect B — unmapped contributor email.** The
  `Contributor Attribution Check` job fails a PR whose commits carry a
  commit-author email with no mapping in the repository.

Both are repository hygiene, not product behavior. Fixing them here keeps the
signal on the PR's actual subject matter.

---

## 2. Defect A — xAI TTS test doubles reject `stream=True`

### Observed shape

`_generate_xai_tts()` (`tools/tts_tool.py`) issues exactly one HTTP call:

```python
response = requests.post(
    f"{base_url}/tts",
    headers={...},
    json=payload,
    timeout=60,
    stream=True,
)
```

`stream=True` is unconditional — it is what lets `_write_tts_response_to_file()`
read the body without materialising it twice. The keyword is production
behavior and is **not** in scope for change.

`tests/tools/test_tts_xai_speech_tags.py` monkeypatches `requests.post` with
plain functions rather than `Mock` objects, so each double's signature *is* the
contract it asserts against. Ten of the fourteen doubles in that file already
declare `stream=False`; four do not, and those four fail with
`TypeError: fake_post() got an unexpected keyword argument 'stream'` — a
signature mismatch raised at call time, before the test's own assertions
execute.

### Intended fix

Add the missing `stream=False` parameter to the four lagging doubles, matching
the convention already established by their ten siblings in the same file.

**Explicitly not done:**

- No change to `tools/tts_tool.py`. The production call is correct; the doubles
  are stale. Were the reverse true — were `stream=True` itself the defect — this
  change would stop and report rather than edit production code.
- No assertion is removed, loosened, or retargeted. The four tests continue to
  assert exactly what they asserted before; they simply reach their assertions.
- No new assertion is added either. Capturing/asserting `stream` is a separate
  (defensible) coverage question, and mixing it in would make the hygiene diff
  harder to review as hygiene.

### Why a default value rather than a required parameter

`stream=False` (defaulted, not required) is the sibling convention in this file
and it keeps each double callable by any caller that omits the keyword. It
mirrors `requests.post`'s own signature, so the double stays a faithful stand-in
rather than a stricter one.

---

## 3. Defect B — unmapped contributor email

### Observed shape

`.github/workflows/contributor-check.yml` collects the distinct author emails of
the PR's commits (`git log <merge-base>..HEAD --format='%ae'`) and fails when an
email is neither auto-resolvable nor mapped. An email is accepted when it:

1. matches a skip case (maintainer, bot, `*@users.noreply.github.com` id+login
   form), or
2. has a file at `contributors/emails/<email>`, or
3. appears as a quoted key in `scripts/release.py`.

The current branch author's commit-author email satisfies none of these, so the
job exits 1.

### Intended fix

Add a single mapping file under `contributors/emails/`, per
`contributors/README.md`:

- **file name** = the exact commit-author email as reported by
  `git log --format='%ae'` for the branch commits;
- **first non-comment line** = the GitHub login;
- an optional `#` comment line recording provenance.

The login is derived from repository-native evidence — the fork's `origin`
remote (`git@github.com:<login>/hermes-agent.git`) identifies the fork owner,
which is the same identity authoring the branch commits.

**Explicitly not done:**

- `AUTHOR_MAP` / `LEGACY_AUTHOR_MAP` in `scripts/release.py` is frozen legacy
  data. `contributors/README.md` and `scripts/add_contributor.py` both say not
  to append to it; the whole point of the per-file directory is that additions
  never merge-conflict. This change adds a file, not a dict entry.
- No change to `.github/workflows/contributor-check.yml`. The job's predicate is
  correct; the repository was simply missing the datum it looks for. Relaxing
  the check would defeat the attribution guarantee it exists to enforce.
- Exactly one mapping is added. Pre-mapping other identities is speculative.

---

## 4. Non-goals

- No production code changes (`tools/`, `agent/`, `gateway/`, `hermes*`).
- No workflow logic changes.
- No dependency, lockfile, or environment changes; no installs.
- No `.env`, credential, or permission changes.
- No broadening of either fix beyond the two observed failures.

---

## 5. Verification plan

Both defects are reproduced from the base *before* the fix and re-run after,
using the repository-provided runner (`scripts/run_tests.sh`) against
already-provisioned tooling:

| Defect | RED (at base) | GREEN (after fix) |
| --- | --- | --- |
| A | the four tests error with `TypeError: ... unexpected keyword argument 'stream'` | all tests in the file pass |
| B | the workflow's mapping predicate finds no `contributors/emails/<email>` and no `release.py` key for the branch author's email | the predicate resolves; `tests/scripts/test_contributor_map.py` stays green |

Runtime results, CI results, and PR custody are recorded but are **not**
self-certified by this change — see the orchestrator gates in the review
contract.
