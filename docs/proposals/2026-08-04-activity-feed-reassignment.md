# Activity as the event log, Feed as a receiver index

**Status:** proposed | **Date:** 2026-08-04 | **Last reviewed:** 2026-08-04

Step 4, item 1 of the activity/feed work. Steps 1–3 landed in #166, #167, #168
and #169; the seam they built (`services/events.py`) is what makes this
tractable. Terminology is in [`docs/glossary.md`](../glossary.md).

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

An earlier draft of this plan said "nullable because `site_broadcast` has no
subject". That was wrong, and checking it is what produced the rule below.
`site_broadcast` has no live emitter and `writes_activity=False`, so it never
reaches the `Activity` table at all. Checked mechanically against the policy
table and the event schemas:

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

**1. Add the column.** Migration adding `activity.subject_user_id`, nullable,
indexed, FK to `user.id`. Nothing reads or writes it yet. Covered by the
migrations CI (#171, extended in #173): one head, builds from scratch, no
model/migration drift, and a downgrade/upgrade round-trip across a *populated*
database with the seeded rows verified afterwards.

**2. Populate it on write.** `events.distribute` already derives the subject —
`deliver()` resolves `subject_id` from the event content to set
`Feed.subject_user_uuid`. The same derivation sets the new column when the
`Activity` is constructed. New rows are complete from here on; old rows are
still null.

**3. Backfill.** Parse `event_json` for every row where `subject_user_id IS
NULL`, extract `subject_id`, write it. Batched and idempotent, so it can be run,
interrupted, and re-run. Note this is a *different* kind of migration from the
one declined in 3b: that was refusing to **correct** wrong rows, this
**derives** a column from data that is already right. Size it first:

```sql
SELECT count(*) FROM activity;
```

**It must skip, not abort.** A row whose payload will not parse, or whose
`subject_id` names a user that no longer exists, is left null and logged. One
unreadable row from some retired code path must not fail the migration for the
whole table — the same reasoning as 3b-1, one layer down.

The migrations CI exercises this for real: its seeded dataset builds
`Activity` rows through `events.distribute`, so a backfill runs against genuine
`event_json` and `verify` fails if it mangles them.

Coverage is thin, though — the dataset distributes only `create_question` and
`answer_question`, 2 of the 15 verbs that write activities. All 15 store
`subject_id` the same way, so one extraction handles them all and the risk is
lower than the count suggests, but broadening the seeded verbs before this step
lands would make the test mean what it appears to mean.

**4. Switch the read path.** `get_activities_v2` splits in two, because they
were always two questions:

| Query | Reads | Ordered by |
|---|---|---|
| receiver feed (`subject_user_uuid is None`) | `Feed` by `receiver_id` | `activity_id desc` |
| subject timeline | `Activity` by `subject_user_id` | `id desc` |

The subject branch needs no dedup, no `limit * 2`, and works for a user with no
audience. Both still materialize per viewer, so the gate above is unchanged.
This is the step where the bug is fixed and the only one with a behavior change.

**5. Delete the dead v1.** `get_activities` has no callers and is already marked
`# TODO to remove this function`. Same category as `new_activity_into_feed`,
which #169 deleted.

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
  queries. Pins the containment described under "Why nullable".

## Open questions

- **Backfill size.** Unknown without `count(*)` against production. It sets
  whether step 3 is a single statement or a batched script.
- **Widen the seeded verbs before step 3?** The migrations CI dataset covers 2
  of the 15 activity-writing verbs. Cheap to extend, and it is what makes the
  backfill test load-bearing rather than decorative.
- **Does the subject timeline want a site filter of its own?** Today the viewer
  gate is per item, applied after the fetch, so a subject with lots of activity
  in sites the viewer cannot read yields a short page rather than an empty one.
  Acceptable, but it is a pagination wrinkle worth knowing about.
