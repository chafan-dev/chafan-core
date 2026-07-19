# 16b: Time Decay on Karma Contributions (Deferred)

**Phase:** 5 — Optional | **Status:** Deferred unless demand emerges

**Source:** `KARMA_OVERHAUL_PLAN.md` Phase 4B.

---

## Concept

Older karma contributions count less than newer ones. Exponential decay with a 2-year half-life is a reasonable starting point:

```
effective_karma_contribution = raw_contribution * exp(-ln(2) * age_years / 2)
```

An answer earning 10 karma when posted 2 years ago contributes ~5 to the author's current karma.

## Implementation sketch (if enabled)

1. Applied in the **batch** `compute_karma` reconciliation, not in incremental updates.
2. Reconciliation runs periodically (via the APScheduler job from `08-rep-manager-centralization.md`), so authoritative karma naturally decays over time.
3. Incremental writes continue to use full contribution values; reconciliation corrects the drift.

## Half-life decision

2-year half-life is a starting estimate. Tune based on:
- Observed distribution of user karma pre- vs post-decay.
- Whether the resulting ordering "feels right" against moderator intuition.

Cannot be set without real data; pick a value at implementation time, observe, adjust.

## Trigger for picking up

Top-karma users are dominated by early adopters whose contributions are years old and no longer reflect current community standing.

## Why deferred

- Requires reconciliation infrastructure to absorb the drift — that's in `08-rep-manager-centralization.md`, which hasn't deployed yet.
- Long-tail behavior change; worth observing karma distribution for a few months after v2 ships before deciding if decay is needed.
