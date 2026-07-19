# 11: OpenAPI Baseline Diff (Lightweight)

**Phase:** 2 — Feature-level | **Effort:** 2-3 hours | **Risk:** None

**Status: Needs further review before implementing.** The `assert current == baseline` design below is brittle to cosmetic noise (FastAPI/Pydantic version bumps reorder dict keys, change descriptions, etc.) — every dep bump would force a baseline regen, which trains contributors to regen-without-reading and kills the signal. Resolve the diff strategy before building. Options to weigh: (a) structured diff via `deepdiff` with ignore-paths for descriptions/examples/ordering, (b) `openapi-diff` which classifies breaking vs non-breaking changes, (c) compare only a stable contract subset (operationId, paths, parameter names/types, response status codes). Pick one and document it before starting.

---

## Problem

The OpenAPI schema exposed by FastAPI changes silently. Backend refactors sometimes break frontend contracts without anyone noticing until a user hits the bug.

## Fix — lightweight baseline diff

Not `schemathesis`, not full contract testing. Just:

1. Commit `tests/openapi_baseline.json` — the current generated OpenAPI schema.
2. Add a CI check that:
   - Generates the current schema.
   - Diffs against the committed baseline.
   - Fails if there is any difference.
3. To accept a schema change, the contributor regenerates the baseline and commits it. The diff in the PR is the contract change, visible for review.

### Implementation sketch

```python
# tests/test_openapi_baseline.py
def test_openapi_schema_matches_baseline():
    from chafan_core.app.main import app
    current = app.openapi()
    with open("tests/openapi_baseline.json") as f:
        baseline = json.load(f)
    assert current == baseline, "OpenAPI schema changed; regenerate baseline if intentional."
```

Add a make target `make regenerate-openapi-baseline` that dumps `app.openapi()` to the file.

## Why not `schemathesis` or property-based API testing

- Much larger time investment.
- Catches a different class of bug (implementation bugs, not contract drift).
- The test suite is limited; property-based API tests require more setup than the current baseline warrants.
- The cheap baseline-diff gives 80% of the "oh, the schema changed" value at 5% of the effort.

## Acceptance

- CI fails on schema drift.
- Intentional schema changes require committing an updated baseline.
- No spurious failures from unordered keys etc. (FastAPI's `app.openapi()` is deterministic for a given code state.)

## Dropped from v1

v1 Proposal 11B — systematic error-path tests — is **not** in v2. Inline bug fixes are covered by `07-test-hygiene.md`. Systematic error-path test coverage is deferred until prod is stable.
