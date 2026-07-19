# 03: Error Message Grammar Fixes

**Phase:** 0 — Quick wins | **Effort:** 1 hour | **Risk:** None

---

## Problem

`chafan_core/utils/base.py` `ErrorMsg` union contains grammar errors, inconsistent casing/punctuation, and one malformed entry:

- `"error_msg,"` — a literal broken string that looks like someone copy-pasted a template.
- Inconsistent tense/capitalization across similar messages.
- Minor typos.

## Fix

1. Proofread all ~131 `Literal[]` entries. Fix typos, standardize punctuation and tense.
2. Delete `"error_msg,"` — verified zero usages outside its own definition.
3. Update any call sites whose literal string changes as a result.

## Decision

- Keep the `Literal` union structure as-is. Do **not** convert to `StrEnum` (see `deferred/errormsg-strenum.md` for rationale).
- Preserve the literal string values visible to frontend/API consumers unless a change is a genuine fix; for changed strings, make sure the frontend doesn't string-match them anywhere. If it does, fix the frontend in lockstep.

## Acceptance

- No typos.
- No malformed entries.
- mypy passes.
- No broken frontend error-handling paths.
