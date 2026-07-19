# 16a: Featured Answer Bonus (Deferred)

**Phase:** 5 — Optional | **Status:** Deferred unless demand emerges

**Source:** `KARMA_OVERHAUL_PLAN.md` Phase 4A.

---

## Concept

When an answer is marked "featured" by a site moderator, its author receives a karma bonus (e.g. +5 global karma, +5 site karma).

## Implementation sketch (if enabled)

1. Add `ANSWER_FEATURED_KARMA = 5` to `rep_manager.py` constants.
2. Add event functions: `rep_manager.award_answer_featured(db, user, answer)`, `rep_manager.revoke_answer_featured(db, user, answer)`.
3. Wire into the site-moderator "feature/unfeature answer" endpoint.
4. Extend `compute_karma` to include featured-answer contributions so reconciliation stays consistent.

## Trigger for picking up

Site owners repeatedly ask for a way to elevate specific answers without manually granting karma via DB edits.

## Why deferred

No concrete demand signal today. Shipping it preemptively adds surface area to `rep_manager` and to `compute_karma` reconciliation logic without a payoff.
