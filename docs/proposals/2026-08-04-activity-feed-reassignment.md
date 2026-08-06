# Activity as the event log, Feed as a receiver index

**Status:** proposed | **Date:** 2026-08-04 | **Last reviewed:** 2026-08-06

Step 4, item 1 of the activity/feed work. Steps 1–3 landed in #166, #167, #168
and #169; the seam they built (`services/events.py`) is what makes this
tractable. The migrations CI this plan's schema change relies on landed in #171
and #173. Terminology is in [`docs/glossary.md`](../glossary.md).

## The problem

`Feed` is a delivery record: one row per `(activity, receiver)`. `Activity` is
the event log. Today the *subject* timeline — "show me everything this user
did", the profile page — is served out of `Feed`:

```python
if subject_user_uuid is not None:
    feeds = feeds.filter_by(subject_user_uuid=subject_user_uuid)
else:
    feeds = feeds.filter_by(receiver_id=receiver_user_id)
```
[`feed_impl.py:144`](../../chafan_core/app/services/feed_impl.py)

The subject branch ignores `receiver_id` entirely, and asks the delivery table a
question about authorship. Three consequences, all live:

**Duplicates are structural.** A user with 200 followers produces 200 `Feed`
rows per activity, so the same activity comes back 200 times. Hence the
`limit * 2` over-fetch and the `activity_ids` seen-set at `feed_impl.py:150-161`
— machinery that exists only to undo the fan-out the query just read.

**A user with no audience has an empty profile.** No followers and no column
subscribers means no `Feed` rows, so the profile timeline is blank no matter how
much the user has posted. This is the bug in its plainest form.

**`Feed` carries a column it should not.** `subject_user_uuid` is denormalized
onto every delivery row purely to make that filter possible
([`models/feed.py:26`](../../chafan_core/app/models/feed.py)).

The now-dead v1 `get_activities` shows what this forced. Viewing your own
profile swapped in the *superuser's* receiver id:

```python
if receiver.uuid == subject_user_uuid:
    receiver_id = crud.user.get_superuser(db).id
```
[`feed_impl.py:180`](../../chafan_core/app/services/feed_impl.py)

— because you do not follow yourself, so you have no `Feed` rows for your own
activity, so your own profile would otherwise be blank. A workaround for
exactly the defect above.

## The target

Two tables, two responsibilities, neither borrowed:

- **`Activity`** — the complete event log, and the source for *subject*
  queries. One row per event.
- **`Feed`** — a pure receiver index. `(activity_id, receiver_id)` and nothing
  else.

## Why this needs a schema change

`Activity` has no subject column. The subject exists only inside `event_json`,
which is `Column(String)` — plain text, not `JSON`/`JSONB`
([`models/activity.py:22`](../../chafan_core/app/models/activity.py)). So
"activities whose subject is user X" is not expressible in SQL today except as
a full scan with a per-row parse, which is worse than the query it replaces.

The addition is one column:

```
activity.subject_user_id   -- nullable, FK to user.id, indexed
```

The alternative — converting `event_json` to `JSONB` with an expression index —
avoids the column but is a type migration on the largest table and yields no
foreign key. Not worth it.

### Why nullable

Not because some verb lacks a subject — the tempting answer, and the wrong one.
`site_broadcast` is the only content type without `subject_id`, but it has no
live emitter and `writes_activity=False`, so it never reaches the `Activity`
table at all. Checked mechanically against the policy table and the event
schemas:

> **Every one of the 15 verbs that writes an `Activity` carries `subject_id`.**
> None are missing it.

So on today's code the column would in fact always be populated. It is still
declared nullable, for two reasons that have nothing to do with any verb:

- **The deploy is two-phase.** Step 1 adds the column before step 3 fills it.
  Between those, every existing row is null.
- **Historical rows may not backfill.** The table holds rows written by code
  that no longer exists. Any whose payload will not parse, or whose
  `subject_id` points at a since-deleted user, cannot be filled and must be
  allowed to stay null rather than block the migration.

Tightening to `NOT NULL` is a later, separate decision, available once a
backfill has run and `SELECT count(*) FROM activity WHERE subject_user_id IS
NULL` is zero. Not part of this plan.

### `site_broadcast`

Low priority, and undecided between removal and refactor — so this plan does
not try to make it correct. It only guarantees it cannot break anything, which
costs nothing here because the null-tolerant design above already covers it:

- a content object with no `subject_id` yields `None` from `_attr`, so step 2
  writes a null and does not raise;
- the backfill skips what it cannot parse rather than aborting (see step 3);
- a null-subject row simply never appears in a subject query.

If `site_broadcast` ever gains an emitter, the worst outcome is that its
activities do not show on anyone's profile. That is a correctness gap in a
component already slated for a decision, not an outage.

## The safety property, verified

Switching the subject query from `Feed` to `Activity` widens what the query
*returns*: previously only activities that had been delivered to somebody, now
everything the subject did. That is the fix, but it raises the obvious
question — does it expose activity from sites the viewer cannot read?

**No.** Delivery has never been what grants visibility. `materialize_activity`
resolves the event per *viewer*, and the responder gate is a site membership
check:

```python
if not user_permission.user_in_site(
    db, site=question.site, user_id=principal_id, op_type=OperationType.ReadSite,
):
    return None
```
[`responders/question.py:63`](../../chafan_core/app/responders/question.py)

`materialize_event` returns `None` when a preview is `None`, so
`materialize_activity` returns `None` and the item silently does not render.
Same guarantee the event-distribution design already rests on: a `Feed` row
grants nothing, and now neither does an `Activity` row.

The one path where that guarantee does *not* hold is
`feed_impl.retrieve_content`, the RSS path — tracked separately as
[#170](https://github.com/chafan-dev/chafan-core/issues/170) and untouched by
this work.

## Steps

Each is independently deployable and independently revertible. Steps 1–3 change
no behavior at all.

**1. Add the column. — done, `7a670908f3fa`, applied to production 2026-08-06.**
Migration adding
`activity.subject_user_id`, nullable,
indexed, FK to `user.id`. Nothing reads or writes it yet. Covered by the
migrations CI (#171, extended in #173): one head, builds from scratch, no
model/migration drift, and a downgrade/upgrade round-trip across a *populated*
database with the seeded rows verified afterwards.

**2. Populate it on write. — done, #178.** `events.distribute` already derived the
subject — `deliver()` resolved `subject_id` from the event content to set
`Feed.subject_user_uuid`. That derivation is now `events._subject_user_of`,
called once when the `Activity` is constructed and passed to `deliver`, so the
two columns cannot disagree: one lookup answers both. New rows are complete
from here on; old rows are still null.

Two tests pin it: `Activity.subject_user_id` and `Feed.subject_user_uuid` name
the same user, and a `subject_id` whose user no longer exists writes a null
rather than raising a foreign key violation into the caller's transaction.

Both live in `test_events_distribute.py`, which — along with
`test_activity_policy.py` — had never run in CI: the unit-tests job named its
files one by one and was last touched in #155, before #167 added them. That
step now takes everything directly under `tests/app/`, by subtraction.

**3. Backfill. — done, `scripts/backfill_activity_subject.py`.** Parse
`event_json` for every row where `subject_user_id IS NULL`, extract
`subject_id`, write it. Batched and idempotent, so it can be run, interrupted,
and re-run. Note this is a *different* kind of migration from the one declined
in 3b: that was refusing to **correct** wrong rows, this **derives** a column
from data that is already right.

A script rather than a migration, deliberately: it keeps a potentially long
`UPDATE` out of the migration chain, and an interrupted run is resumed by
running it again rather than by a downgrade. It is meant to be deleted once
production has no null subjects left.

### What production actually looks like

Measured 2026-08-06, and it settles most of what this section used to leave
open:

| | |
|---|---|
| rows | 412 (344 kB), oldest 2025-07-06 |
| `subject_user_id` populated | 0 — step 2 was merged but **not yet deployed** |
| payloads that will not parse | 0 |
| payloads with no `subject_id` | 0 |
| subjects naming a deleted user | 0 |
| verbs present | 10 of the 15 |

At 412 rows this is a single statement that finishes instantly; the batching
exists for the table this becomes, not the table it is. Every row is readable
and every subject resolves, so the skip paths below are — today — defensive
rather than load-bearing. They stay, because "today" is the wrong thing to
build a data migration on.

Because step 2 is not deployed yet, **run the script after that deploy**, or
run it again afterwards: anything written while the old code is still live
lands with a null subject.

**It must skip, not abort.** A row whose payload will not parse, or whose
`subject_id` names a user that no longer exists, is left null and logged. One
unreadable row from some retired code path must not fail the migration for the
whole table — the same reasoning as 3b-1, one layer down.

This is also why the extraction is Python rather than
`event_json::jsonb -> 'content' ->> 'subject_id'` in SQL: the cast raises on
the first malformed row and takes the whole statement with it, and
`pg_input_is_valid` is PostgreSQL 16+ while production is 14.

### How it is tested

The migrations CI owns the only populated database in CI, which is what a
backfill needs — but since step 2 the seed writes `subject_user_id` on every
row, so running the script there as-is would find nothing to do and pass
without proving anything. The job nulls the column first to recreate the state
production is in, then asserts the script restores a fingerprint of exactly
what `events.distribute` wrote.

That construction also dissolves what this section used to flag as thin
coverage. The test no longer depends on how many verbs `_build_deep` seeds,
because it never names a verb: it compares the backfill's output against the
application's own writes, whatever those happen to be. Widening the seeded
verbs is still worth doing for its own sake, but it is no longer a
prerequisite here.

**4. Switch the read path.** `get_activities_v2` splits in two, because they
were always two questions:

| Query | Reads | Ordered by |
|---|---|---|
| receiver feed (`subject_user_uuid is None`) | `Feed` by `receiver_id` | `activity_id desc` |
| subject timeline | `Activity` by `subject_user_id` | `id desc` |

The subject branch needs no dedup, no `limit * 2`, and works for a user with no
audience. Both still materialize per viewer, so the gate above is unchanged.
This is the step where the bug is fixed and the only one with a behavior change.

**The identifier changes type here, which is easy to miss.** The API takes
`subject_user_uuid: Optional[str]`
([`endpoints/activities.py:47`](../../chafan_core/app/api/api_v1/endpoints/activities.py)),
and `Feed.subject_user_uuid` is a `CHAR` column, so today the parameter reaches
the query unchanged. `Activity.subject_user_id` is an integer FK, so the subject
branch has to resolve the uuid to a user first. Two consequences worth deciding
deliberately rather than discovering:

- a uuid that names no user returns an **empty timeline**, not an error — it is
  a reader asking about somebody who is gone, not a malformed request;
- that lookup is one extra query per call, which is why it belongs in the
  subject branch only and not above the split.

Keeping the API parameter a uuid is deliberate: it is the public identifier and
changing it would break clients for no gain.

**5. Delete the dead v1. — done, #180.** `get_activities` had no callers and was
already marked `# TODO to remove this function`. Same category as
`new_activity_into_feed`, which #169 deleted. It was also the last caller of
`execute_with_broker` in `feed_impl`.

**6. Deferred — drop `feed.subject_user_uuid`.** Destructive DDL, and
contingent on step 4 item 2 (fan-out-on-write vs read-time resolution): under
read-time resolution there may be no `Feed` rows at all, which makes the column
moot rather than merely redundant. Hold until that is decided.

## What changes for users

Profile timelines start showing everything the subject did that the viewer is
allowed to see, rather than only what happened to be delivered to somebody.
For an active user with followers the result is nearly identical, minus the
duplicates. For a user with no followers it goes from empty to complete.

This is the intended fix, but it is a visible product change and worth
confirming before step 4 ships.

## Verification

Per step: full unit suite, byte-identical OpenAPI (the endpoint signature does
not change at any point), both architecture ratchets, mypy flat, and the
migrations CI (#171, #173).

Three tests the change should carry:

- A user with **no followers and no column subscribers** has a non-empty
  profile timeline. This fails today and is the point of the change.
- A viewer who cannot read a private site does **not** see the subject's
  activity from that site, even though the `Activity` row is now reachable by
  the query. Pins the safety property above.
- An `Activity` whose payload has no resolvable subject is **skipped, not
  fatal** — it backfills to null, writes to null, and is absent from subject
  queries. Pins the containment described under "Why nullable". The *writes to
  null* half landed with step 2; the other two halves belong to steps 3 and 4.

## Open questions

- ~~**Backfill size.**~~ Answered 2026-08-06: 412 rows, 344 kB. Step 3 is a
  script for the shape of the job, not for the size of it.
- ~~**Widen the seeded verbs before step 3?**~~ No longer a prerequisite — the
  backfill test compares against what `events.distribute` wrote rather than
  against a fixed list of verbs, so it is load-bearing at any seed width. Still
  worth doing on its own merits.
- **Does the subject timeline want a site filter of its own?** Today the viewer
  gate is per item, applied after the fetch, so a subject with lots of activity
  in sites the viewer cannot read yields a short page rather than an empty one.
  Acceptable, but it is a pagination wrinkle worth knowing about.
