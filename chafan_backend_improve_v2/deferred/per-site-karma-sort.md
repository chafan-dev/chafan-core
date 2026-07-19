# Deferred: Per-Site Karma in Profile Ordering

**Source:** v1 `proposals/12-per-site-karma-sort.md` (was Phase 2 in early v2 draft).

**Status:** Deferred. Profile.karma is frozen by `08-rep-manager-centralization.md`.

---

## Summary of the proposal

Sort the contributors list (and any other site-scoped user list) by per-site karma:

```
ORDER BY Profile.karma DESC, User.karma DESC, User.id ASC
```

Today the ordering either uses global karma directly or isn't consistent across endpoints.

## Why deferred

- **Per-site karma is vestigial.** PWA shows global karma everywhere. Only the contributors-list sort consumes `Profile.karma`.
- **Modders are split** on whether they want per-site reputation. No clear demand signal.
- **Maintenance cost is real.** Writing `Profile.karma` doubles the rep_manager event surface and creates a second drift axis (User.karma vs Profile.karma) — for a feature with no committed consumer.
- Per project memory and README principle 7 (avoid DB migrations), the right move is to freeze the column rather than maintain it actively or drop it.

`08-rep-manager-centralization.md` therefore stops writing AND stops reading `Profile.karma`. Contributors sort falls back to `User.karma DESC, User.id ASC`. The column stays in the DB (no migration) so this decision is reversible.

## Trigger for revisiting

- A site moderator explicitly requests per-site contributor ordering and is willing to accept the maintenance cost.
- A product feature emerges where global karma is genuinely the wrong signal (e.g. multi-community discovery, per-site moderator privileges).

## If revisited — what to reconsider

- Whether to revive `Profile.karma` writes or use a cheaper substitute (activity count on the site, last-N-days post count). Substitutes don't drift and don't need reconciliation.
- Whether site-scoped reputation should live on `Profile` at all, or in a separate per-site stats table.
- The original v1 acceptance criteria still apply if revived: deterministic ordering, no N+1.

## Prerequisites (before picking this up)

- `08-rep-manager-centralization.md` has shipped — without it, reviving Profile.karma writes lands on the same scattered-mutation problem 08 solved.
- A modder request or product driver concrete enough to justify the maintenance cost.
