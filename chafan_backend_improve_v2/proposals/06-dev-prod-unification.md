# 06: Dev/Prod Environment Unification

**Phase:** 1 — Code correctness | **Effort:** 1-2 days | **Risk:** Medium

---

## Guiding principle

Replace `is_dev()` behavior switches with explicit config flags that default to the same value in all environments. If it works in dev, it works in prod.

---

## Scope changes from v1

The original Proposal 07 had 8 sub-items (A1-A8). v2 splits the scope:

| Sub-item | Status |
|----------|--------|
| A1 — Caching disabled in dev | **Moved to Phase 3** (`13-cache-scope-reduction.md`). Enabling dev cache is subsumed by a larger cache refactor. |
| A2 — Rate limiting disabled in dev | **In scope here.** |
| A3 — Initial coins differ (100 vs 0) | **In scope here. Unify to 0.** No dev coin-grant helper — if needed, modify DB directly or add an admin-only API endpoint later. |
| A4 — Site creation bypasses karma in dev | **In scope here. Remove the `is_dev()` bypass.** |
| A5 — Search returns all results in dev | **Superseded by `09-adaptive-search-index.md`.** Not touched here. |
| A6 — Upload mock URLs / skip auth | **Superseded by Phase 4** (`15-image-upload-r2.md`). Do **not** modify upload code in this proposal. |
| A7 — Form reward UUID check skipped | **Moved to `12-seed-unification.md`.** The UUID-in-env approach reveals a broader pattern (multiple components assume pre-seeded rows identified by env-var UUIDs). `12` addresses the class; do not handle A7 here. |
| A8 — Error handling differs | **In scope here.** Unify on log + Sentry (no `raise` in dev). |
| Debug bypass startup checks | **In scope here.** |

---

## A2. Rate limiting unified

**Files:** `chafan_core/app/common.py`, `chafan_core/app/limiter.py`, `chafan_core/app/main.py`.

Replace `FORCE_RATE_LIMIT` with `DISABLE_RATE_LIMIT`, defaulting `False` everywhere. Tests that make many calls should either fall under the existing lenient limit (150/min) or explicitly clear the limiter in a fixture via `limiter.reset()` (or equivalent `clear_limits_for_ip()` helper).

Do **not** disable the limiter by default in tests — that hides bugs where the limiter itself is misconfigured.

## A3. Initial coins unified to 0

**File:** `chafan_core/app/crud/crud_user.py` (lines 75-76 in v1 reference).

Replace the dev branch with `settings.INITIAL_USER_COINS` defaulting to `0` in all environments. Tests that need a user to have coins use the existing `ensure_user_has_coins()` helper in `conftest.py:185`.

No `make` target, no env-specific seed script. If the developer needs coins for manual testing, they can:
- Run SQL directly.
- Add an admin-only API (future, not part of this proposal).

## A4. Site creation karma bypass removed

**File:** `chafan_core/app/materialize.py` (lines 254-258 in v1 reference).

Delete `or is_dev()` from `can_create_*_site`. Tests that exercise site creation use fixtures that grant the required karma explicitly.

## A7 — moved to `12-seed-unification.md`

The original A7 planned to remove the dev bypass on form-reward UUID validation by setting `WELCOME_TEST_FORM_UUID` in `.env.example`. That's symptom treatment. The underlying issue is that several components assume pre-seeded DB rows identified by UUID env vars (welcome form, possibly others). `12-seed-unification.md` addresses the class: centralize seed data into `init_db.seed_dev_data()` and delete the UUID env vars.

Do not touch the form-reward UUID path in this proposal. It lands with `12`.

## A8. Error handling unified

**Files:** `chafan_core/app/common.py` (lines 178-190), `chafan_core/app/main.py` (lines 82-86), `chafan_core/app/materialize.py` (lines 762-770).

Unified behavior (no environment branches):

```python
def handle_exception(e: Exception) -> None:
    logger.exception("unhandled exception")
    if settings.SENTRY_DSN:
        sentry_sdk.capture_exception(e)
    # do not raise — let the outer handler turn this into the standard 500 response
```

Sentry is actively used today (20 call sites verified). Keeping the `if settings.SENTRY_DSN` guard lets dev opt out by simply not setting the DSN, without needing `is_dev()`.

Do **not** re-raise in dev. That was a dev convenience to get tracebacks in the terminal; the logger handles that cleanly, and raising in dev but not prod is exactly the kind of divergence this proposal is eliminating.

### Trade-off for tests

Today's dev re-raise also incidentally helped pytest see the original exception. After unification, a test that hits a handler-caught exception will see a 500 response with the traceback only in the captured log output — not bubbled up to the assertion. This is worse for debugging an unexpected exception in a test.

Accepted trade-off. No flag, no test-only override. When debugging a test that hits a 500:
- Check pytest's captured log output for the `unhandled exception` log line and traceback.
- Or temporarily make `handle_exception` re-raise locally while iterating.

If this becomes painful in practice, revisit (a thin `RAISE_HANDLED_EXCEPTIONS` env flag for the test environment is the obvious escape hatch). Don't preempt — see if it's actually a problem first.

---

## Debug bypass startup safety checks

Three flags are currently not gated by environment and can be activated anywhere:

1. `DEBUG_BYPASS_BACKEND_CORS == "magic"` — CORS `*`
2. `DEBUG_BYPASS_REDIS_VERIFICATION_CODE` — bypasses email verification
3. `DEBUG_ADMIN_TOOL_FULL_SITE_PASSCODE == "5e5da072"` — hardcoded default

Add assertions at app startup:

```python
if settings.ENV == "prod":
    if settings.DEBUG_BYPASS_BACKEND_CORS == "magic":
        raise RuntimeError("DEBUG_BYPASS_BACKEND_CORS='magic' is not allowed in prod")
    if settings.DEBUG_BYPASS_REDIS_VERIFICATION_CODE:
        raise RuntimeError("DEBUG_BYPASS_REDIS_VERIFICATION_CODE must be unset in prod")
    if settings.DEBUG_ADMIN_TOOL_FULL_SITE_PASSCODE == "5e5da072":
        raise RuntimeError("DEBUG_ADMIN_TOOL_FULL_SITE_PASSCODE must be changed from default in prod")
```

Prefer startup failure over silent production compromise.

---

## Acceptance

- `is_dev()` call count drops to ~18 (from 26 baseline) after this proposal alone — the remaining ~18 are owned by other proposals: cache paths by `13`, upload paths by `15`, search paths by `09`, seed/UUID paths by `12`. The full drop to a small residual (logging output, OpenAPI docs visibility, email mock) is a v2-wide outcome, not a `06`-alone outcome.
- Within `06`'s scope: rate limiter, coin initialization, karma-for-site-creation, and error handling all run identical code in dev and prod.
- Prod startup fails loudly if any debug bypass is misconfigured.
- Image upload (A6) remains completely untouched here — Phase 4 owns it.
- Form-reward UUID validation (A7) remains completely untouched here — `12-seed-unification.md` owns it.

## Test plan

After each sub-item, run full test suite. For A2 (rate limiting), verify the existing tests still pass without needing a blanket bypass — if any tests hit the limit, add an explicit `limiter.reset()` fixture, not a global disable.
