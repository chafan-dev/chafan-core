# 08: rep_manager Centralization (Karma + Coin Routing)

**Phase:** 1 — Code correctness | **Effort:** 2-3 days | **Risk:** Medium

**Source plan:** `/var/home/lizhenbo/src/chafan/KARMA_OVERHAUL_PLAN.md`

**Depends on:** `04-scheduled-consolidation.md` (APScheduler slot for the reconciliation job).

---

## Goal in one line

**Centralize all karma/coin mutation code in one place so future rule changes and audit are maintainable.** Atomicity and correctness-chasing are not goals of this proposal (coins are anti-spam, not currency; see project memory).

## Problem

Karma and coin mutations are scattered across endpoints, CRUD helpers, and ad-hoc `user.karma += N` / `user.remaining_coins -= M` writes. Consequences:

- Changing a karma rule (e.g. "+10 on answer create") requires finding every call site.
- The batch `compute_karma()` in `scheduled/lib.py:57` hardcodes its own rule numbers, which can silently drift from the incremental writes scattered elsewhere.
- Coin deductions are similarly scattered, and the future image-upload coin hook (`15-image-upload-r2.md`) has no clean place to plug in.

## Status quo — what exists today

- **`chafan_core/app/rep_manager.py` already exists as a stub.** Seven stub functions (`new_submission_suggestion`, `new_question`, `new_submission`, `accept_submission_suggestion`, `new_answer_suggest`, `accept_answer_suggest`, `new_article`) all `pass`. Header TODO dated 2025-07-08 reads: "everything about user permission, including if they can create a site (KARMA), invite a user, write an answer, etc, should be moved into this file. Coin payment and karma update should go to this file."

  The stubs' naming (verbs on bare objects) does not fit an award/revoke model. This proposal renames them as part of the rewrite — see "Naming" below.

- **`chafan_core/scheduled/lib.py:57` has `compute_karma(user) -> Tuple[int, Mapping[int, int]]`** — returns global karma plus per-site karma dict. Rule numbers are hardcoded in this function (base + upvotes for answers, questions, submissions, articles; +2 per comment; +2 per non-empty profile field; `min(len, 5) * 2` for work/education experiences).

- **`refresh_karmas()` at `scheduled/lib.py:146`** iterates every active user, recomputes karma, writes both `user.karma` and `profile.karma`.

- **`crud_coin_payment.py:make_payment`** is a transfer primitive (deducts payer, credits payee, single commit). It has 7 call sites across the codebase. This proposal routes its body through `rep_manager` without changing the transfer semantics.

## Per-site karma is out of scope

`Profile.karma` (per-site karma) is **not maintained by rep_manager**. The per-site karma sort proposal (v1's `12-per-site-karma-sort.md`) is moved to `deferred/per-site-karma-sort.md`. Rationale:

- Per-site karma is vestigial — the PWA shows global karma everywhere, only one sort consumes it, modders are split on whether they want it.
- Maintaining it doubles the write surface and the drift surface for no current user-visible payoff.
- Per the README's "avoid DB migrations" principle and the project memory on coin/karma drift tolerance, the right move is to stop writing/reading `Profile.karma` (Level B: freeze the column) rather than ALTER TABLE.

This proposal therefore touches only `User.karma` and `User.remaining_coins`. Contributors-list sort and any other reader of `Profile.karma` falls back to `User.karma DESC, User.id ASC` as part of this proposal.

## Naming

Rename the existing stubs to an award/revoke event vocabulary. This is mechanical — the stubs are unused.

| Current stub | Replacement |
|--------------|-------------|
| `new_question(question)` | `award_question_created(db, user, question)` |
| `new_submission(submission)` | `award_submission_created(db, user, submission)` |
| `new_submission_suggestion(ss)` | `award_submission_suggestion_created(db, user, ss)` |
| `accept_submission_suggestion(ss)` | `award_submission_suggestion_accepted(db, user, ss)` |
| `new_answer_suggest(as_)` | `award_answer_suggest_created(db, user, as_)` |
| `accept_answer_suggest(ase)` | `award_answer_suggest_accepted(db, user, ase)` |
| `new_article(article)` | `award_article_created(db, user, article)` |

Plus new functions (not in stub today): `award_answer_created`, `award_answer_upvote` / `revoke_answer_upvote`, `award_question_upvote` / `revoke_question_upvote`, `award_comment_created`, etc. — one event pair per mutation path found during migration step 2.

## Fix — Phase 1 scope

`rep_manager.py` becomes an **event-oriented service** (not a god module):

```python
# rep_manager.py — target shape
ANSWER_CREATE_KARMA = 10
ANSWER_UPVOTE_KARMA = 10
QUESTION_CREATE_KARMA = 5
# ... shared constants, referenced by both incremental path and compute_karma

def award_answer_created(db, user, answer) -> None: ...
def revoke_answer(db, user, answer) -> None: ...
def award_answer_upvote(db, user, answer) -> None: ...
def revoke_answer_upvote(db, user, answer) -> None: ...
# ... one function per domain event

def deduct_coins(db, user, amount: int, reason: str) -> None: ...
def award_coins(db, user, amount: int, reason: str) -> None: ...

def compute_karma(db, user) -> int:
    """Recompute authoritative total karma from scratch, using the constants above."""
    ...
```

Hard rules for these functions:

- **Shared constants** used by both incremental updates and `compute_karma`. No duplicated rule numbers.
- **No schema changes.** `User.karma` stays as is. `Profile.karma` column stays in the DB but is no longer written or read.
- **Coins are anti-spam, not currency.** `make_payment` is routed through `rep_manager` (`deduct_coins` on payer + `award_coins` on payee + CoinPayment row insert) but not atomically hardened — that's cleanup, not urgent. Per project memory: drift is tolerable; long-term maintainability beats correctness chasing.

## `compute_karma` migration

The existing `compute_karma` in `scheduled/lib.py:57` returns `Tuple[int, Mapping[int, int]]` (global + per-site). Target:

1. Move `compute_karma` into `rep_manager.py`.
2. Simplify the signature to `compute_karma(db, user) -> int` — drop the per-site dict.
3. Replace hardcoded rule numbers with the module-level constants that `award_*` functions also use.
4. `scheduled/lib.py` keeps `refresh_karmas()` as the scheduled-job entrypoint but imports `compute_karma` from `rep_manager`.

## Migration steps

1. Write the event/constant/coin/compute_karma surface in `rep_manager.py`. Replace the seven stubs.
2. Grep every `user.karma += N` / `user.karma -= N`. Route each call site through the corresponding `rep_manager.award_*` / `revoke_*` function.
3. Grep every `user.remaining_coins += N` / `-= N`. Route through `rep_manager.deduct_coins` / `award_coins`. This includes `crud_coin_payment.make_payment`, whose body becomes `deduct_coins(payer, amount, reason) + award_coins(payee, amount, reason) + CoinPayment row insert` in a single commit — same behavior, just via the centralized functions.
4. Grep every `profile.karma += N` / `profile.karma -= N` and **delete** (no replacement). Per-site karma is frozen.
5. Grep every read of `Profile.karma` (today: `recs/ranking.py:69-70`'s `rank_site_profiles` and possibly others). Rewrite to sort by `User.karma DESC, User.id ASC`. See `14-n-plus-one-with-link-preview.md` for the eager-load ripple this creates.
6. Rewrite `scheduled/lib.py:refresh_karmas` to:
   - Call `rep_manager.compute_karma(db, user)` for each user (returns int; `User.karma` only).
   - Compare against the stored `User.karma`.
   - **Log drift to a dedicated `chafan.karma_drift` logger**, not Sentry:
     - `logger.warning(...)` when drift > 5
     - `logger.error(...)` when drift > 50
   - Update stored value to the computed authoritative value.
   - Do **not** touch `Profile.karma`.
   - Scheduled hourly (or daily — tune after observing real drift).
7. Run `refresh_karmas` manually once after deploy to establish a baseline. Any drift at that point is pre-existing.

## Coin mutation routing

Every coin change in the codebase must go through `rep_manager.deduct_coins(user, amount, reason)` or `rep_manager.award_coins(user, amount, reason)`. No direct `user.remaining_coins` writes.

The `reason` string is a tag for logs/audit — use stable, grep-able values: `"question_ask"`, `"image_upload"`, `"coin_payment_in"`, `"coin_payment_out"`, `"admin_grant"`, etc.

## Dependency with `04-scheduled-consolidation.md`

- `04` adds the APScheduler slot for `refresh_karmas`.
- `08` rewrites the body of that job.
- If `04` lands first: the job runs the legacy batch body until `08` replaces it. Fine.
- If `08` lands first: the reconciliation code exists but has nowhere to be scheduled from. Do not land `08` before `04`.

## Dependency with `15-image-upload-r2.md`

Image upload's optional coin hook routes through `rep_manager.deduct_coins(user, 1, "image_upload")`. This proposal defines the contract; Phase 4 uses it.

## Dependency with `14-n-plus-one-with-link-preview.md`

Step 5 above forces sort-paths that previously hit `Profile.karma` to now hit `User.karma`, which means loading `Profile.user` for the sort key. `14` owns the eager-load fix for the affected endpoints.

## Acceptance

Aligned with `07-test-hygiene.md` "prod-first" stance — tests may need rewriting, that's acceptable.

- `rep_manager.py` contains all event functions, shared constants, `compute_karma(db, user) -> int`, `deduct_coins`, `award_coins`. The seven original stubs are gone (renamed/absorbed).
- Zero direct writes to `User.karma`, `User.remaining_coins` outside `rep_manager` (grep verification).
- Zero writes to `Profile.karma` anywhere in the codebase (frozen column).
- Zero reads of `Profile.karma`; sort paths use `User.karma DESC, User.id ASC`.
- `refresh_karmas` uses `rep_manager.compute_karma`, runs on APScheduler, logs drift to `chafan.karma_drift`, does not go to Sentry.
- One clean baseline drift-log entry after initial deploy.
- Tests either pass as-is or are rewritten to match the new surface. Rewriting old tests to match the new mutation routing is expected and within scope.

## Out of scope (deferred to Phase 5)

- Featured-answer bonus (`phase5-optional/16a-featured-bonus.md`)
- Time decay (`phase5-optional/16b-time-decay.md`)
- Concentration penalty (`phase5-optional/16c-concentration-penalty.md`)
- Provisional trust (`phase5-optional/16d-provisional-trust.md`)

## Out of scope (permanently, per KARMA_OVERHAUL_PLAN.md constraints)

- DB schema changes (per README principle 7).
- `make_payment` atomicity hardening. Routing through `rep_manager` is the centralization goal; conditional UPDATE / row locking is not.
- PWA `siteKarmas` display cleanup (frontend, out of scope for v2).
- Per-site karma maintenance (deferred — see `deferred/per-site-karma-sort.md`).
