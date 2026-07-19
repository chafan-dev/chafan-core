# 16d: Provisional Trust for New Users (Deferred)

**Phase:** 5 — Optional | **Status:** Deferred unless demand emerges

**Source:** `KARMA_OVERHAUL_PLAN.md` Phase 4D.

---

## Concept

New users start with a "provisional" trust level that dampens their karma contributions and privileges until they clear a ramp-up threshold (account age + basic activity + minimum karma).

Sample rules:
- First 7 days OR first 50 karma: provisional.
- Provisional user actions contribute at 50% of normal karma.
- Provisional user can't moderate or trigger high-privilege actions.

## Implementation sketch (if enabled)

1. Add a `User.is_provisional` derived property (not stored — computed from age + karma).
2. `rep_manager` event functions check `is_provisional(user)` and halve (or similar) the contribution.
3. Privilege checks elsewhere gate on `is_provisional`.

## Trigger for picking up

- Spam account pattern: create account → immediately post → farm karma → abuse privileges.
- Need to rate-limit reputation earning during the new-user window.

## Why deferred

- Spam volume is manageable today via other means (email verification, rate limits).
- Adds complexity to every karma-earning code path; only worth it if the abuse pattern materializes.
- Ramp-up thresholds require tuning against real signup data.
