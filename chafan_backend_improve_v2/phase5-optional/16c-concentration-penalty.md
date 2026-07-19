# 16c: Concentration Penalty (Deferred)

**Phase:** 5 — Optional | **Status:** Deferred unless demand emerges

**Source:** `KARMA_OVERHAUL_PLAN.md` Phase 4C.

---

## Concept

Cap the karma contribution of any single answer (or other single item). A user earning 500 karma from one viral answer shouldn't displace a user earning 500 karma from 100 evenly-rated answers in the reputation ordering.

Example cap: any single item contributes at most `min(raw_contribution, CONCENTRATION_CAP)` where `CONCENTRATION_CAP` might be ~50.

## Implementation sketch (if enabled)

1. Applied in `compute_karma` reconciliation.
2. Cap each contribution individually before summing.
3. Incremental updates continue to pay out full values; reconciliation caps the stored total.

## Trigger for picking up

- A spam/gaming pattern emerges where a user farms karma from one answer via vote manipulation.
- Moderators request that "one-hit wonder" users not be overrepresented in contributor rankings.

## Why deferred

No evidence of the gaming pattern today. Adding a cap preemptively could unfairly penalize legitimately popular answers.
