# Event distribution: one seam for Activity, Feed and Notification

**Status:** 3a landed; 3b-1 done, 3b-2 next | **Date:** 2026-08-03 | **Last reviewed:** 2026-08-04

Step 3 of the activity/feed work. Step 1 (the per-verb policy table) and step 2
(Tier 1 renames) landed in #166 as `ca23ef7`. Step 3a landed in #167 as
`773e8b0`; the sections below are kept in the tense they were written in, and
"Implementation notes" records where the implementation departed from them.

Terminology is defined in [`docs/glossary.md`](../glossary.md). The per-verb
matrix lives in
[`services/activity_policy.py`](../../chafan_core/app/services/activity_policy.py).

## The problem this solves

An event that has happened must reach every sink policy says it belongs in.
Today ~27 call sites each decide that independently, split across two layers,
and nothing checks that a verb is handled consistently. Two live consequences:

- `create_article` has three emitters, so publishing one article writes two or
  three `Activity` rows and only one of them fans out.
- Article-column subscribers get a `Notification` but no `Feed` row, because
  the two deliveries are decided in different places.

## The seam

```python
# chafan_core/app/services/events.py

def distribute(ctx: RequestContext, event: EventInternal) -> Optional[Activity]
```

Two arguments. Everything else is derived: the verb selects the policy row, and
the content's ids resolve the site, the feed audience, and the notification
receivers. Nothing about routing is passed in by the caller, so no caller can
get it wrong.

`distribute` rather than `emit`/`publish`/`dispatch`: `publish` collides with
`is_published` (42 uses, meaning content draft-vs-live); `emit` and `dispatch`
both suggest a queue, and this function writes rows synchronously in the
caller's transaction.

### Duty

Given an event that has already happened, put it in every sink policy says it
belongs in — and nowhere else.

1. Look up `POLICY[event.content.verb]`.
2. Write **exactly one** `Activity`, if the verb is publishable.
3. Resolve `feed_audience` → `deliver(activity, receiver_ids)` → `Feed` rows.
4. Resolve `notifies` → `Notification` rows, then push each.
5. Return the Activity, so callers that need its id have it.

### Explicitly not its duty

- **The transaction.** Never commits, never spawns a background task; writes
  into the caller's session. `check_service_commits.py` enforces this.
- **Timing.** Callers keep their current phase, so introducing the seam changes
  no latency. See "the split this does not fix" below.
- **The domain write.** The question/answer/vote already exists.
- **Whether the event happened.** Conditions like `was_published` are domain
  state and stay in the caller. The table answers *where an event goes*, not
  *whether one occurred*.
- **`CoinPayment`.** A transfer with a payer, payee and amount that happens to
  store an event as its reason. Recorded in the table, not acted on here.
- **Deduplication.** One call, one Activity. Collapsing repeats would hide the
  `create_article` triple-emit rather than expose it.

### Why audience bugs are cheap

Delivery is not visibility. A `Feed` row grants nothing: `materialize_activity`
runs the full responder permission check per receiver at read time and returns
`None` if they cannot read the content. A wrong audience yields an item that
silently does not render, not a leak.

The exception, and the reason it is tracked separately, is
`feed_impl.retrieve_content` — the RSS path dereferences event ids *without*
that check.

## What moves

`check_layer_imports.py` forbids crud importing services, so nine emissions
cannot stay where they are. Each has exactly one service caller, so the
relocation is mechanical:

| From | To |
|---|---|
| `crud_article.create_with_author` | `services/articles.py:232` |
| `crud_article.upvote` | `services/articles.py:400` |
| `crud_submission.create_with_author` | `services/submissions.py:213` |
| `crud_submission.upvote` | `services/submissions.py:390` |
| `crud_answer.upvote` | `services/answers.py:430` |
| `crud_question.upvote` | `services/questions.py:396` |
| `crud_user.add_follower` | `services/me.py:257` |
| `crud_user.subscribe_article_column` | `services/me.py:572` |
| `crud_message.create_with_author` | `services/messages.py:33` |

Two of these **collapse two calls into one**, which is the whole point in
miniature:

- `upvote_answer` — Activity in `crud_answer.upvote`, Notification in
  `services.answers.upvote_answer`. One event, two layers, two hand-derived
  receiver decisions. Becomes one `distribute()` call.
- `follow_user` — identical shape (`crud_user.add_follower` /
  `services.me.follow_user`).

Also moving: `push_notification` leaves `crud_notification.create_with_content`
for `distribute()`, resolving the standing `FIXME crud layer should not call
higher level components`. `create_with_content` becomes a plain persist.

Note that the notification *write* path has no service home today —
`services/notifications.py` is read-side only. That is part of why it is
scattered.

## Audience resolvers

One function per `Audience` member, `(ctx, event) -> set[int]`. 16 of the 17
resolve from ids the event already carries (`ANSWER_BOOKMARKERS` →
`answer.bookmarkers`, `REWARD_GIVER` → `reward.giver`, `CHANNEL_MEMBERS` →
`channel.members`).

`MENTIONED_USERS` is the exception: the handles come from the request payload,
not the event — `MentionedInCommentInternal` carries only `comment_id`. Leave
`notify_mentioned_users` outside `distribute()` and mark it in the table rather
than bending the signature for one case.

The `Exclusion` members already cover the conditional branches; the five
`author_id != receiver_id` guards in `postprocess_new_comment` are all
`Exclusion.SUBJECT`.

## Callers afterwards

The rule: **whoever owns the use case, at the point where the thing is already
durable.** Not endpoints (they queue background tasks), not crud (forbidden,
and it does not know the use case).

- **Phase 1, in-request services** (~15): the nine relocated above, plus
  `questions.invite_answer`, `rewards.create_reward`, `rewards.claim_reward`,
  `sites.apply_join_site`, `sites.create_site` (for
  `create_site_need_approval`), `users.invite_user_to_site`.
- **Phase 2, post-response `postprocess`** (~9): `postprocess_new_question`,
  `postprocess_new_answer` (two verbs), `postprocess_new_article`,
  `postprocess_updated_article`, `postprocess_new_comment`,
  `postprocess_updated_question`, `postprocess_new_submission_suggestion`,
  `postprocess_new_answer_suggest_edit`, plus `notify_mentioned_users`.

### The split this does not fix

Which phase a verb emits in is historical, not principled — nothing justifies
upvotes emitting in-request while questions emit post-response. `distribute()`
preserves the split exactly, which is what keeps 3a neutral. Rationalizing it
belongs with the outbox question in step 4.

## Scope: 3a and 3b

**3a — behavior-neutral. Landed in #167 (`773e8b0`).** Introduce `distribute()`,
move the nine emissions up, route all 27 sites through it. Proven the same way
#166 was: byte-identical OpenAPI, full unit suite (426 passed, 9 skipped), both
ratchets clean, mypy unchanged at 956 errors, plus
`tests/app/test_events_distribute.py` pinning that every verb still reaches the
same sinks. Large diff, no behavior change.

**3b — the fixes 3a makes obvious.** Small diff, real behavior change, reviewed
on its own merits. Split again on the same principle, so the safety net lands
before the change that needs it:

- **3b-1, containment.** `distribute()` degrades instead of raising when an
  audience cannot be resolved. No audience changes, so nobody's feed or inbox
  moves. Landed first because every later change is safer behind it.
- **3b-2, the article fixes.** The duplicate `create_article` emit, drafts
  writing activities, and column subscribers getting a notification but no feed
  row. These are one story — publishing an article distributes it exactly once,
  to everyone it should reach.

**No data migration.** Owner's call, 2026-08-04: tolerate what is already in the
table and fix only new events. Duplicate rows are cosmetic and articles that
already published silently stay that way. The one place stale rows could still
bite is `feed_impl.retrieve_content`, which is fixed in code rather than data —
see below.

Keeping 3a and 3b apart matters because the neutrality argument is otherwise
unavailable exactly where the diff is largest.

### Corrections to the 3b list

Both found by reading the code before starting, 2026-08-04.

**It is a double-emit, not a triple.** Every article lifecycle produces exactly
two `Activity` rows, never three. `postprocess_new_article` runs only when the
article is created published; `postprocess_updated_article` emits only when
`not was_published`; `is_published` is never reverted. The two are therefore
mutually exclusive per article, and the count is always `articles.create_article`
plus exactly one of them. `activity_policy`'s note still says "two or three".

**The draft path is worse than "drafts write activities".** An article created
as a draft and published later gets *no distribution at all*: the Activity is
written at draft time, and the publish transition is `sinks={ACTIVITY}` — no
fan-out, no column-subscriber notification. The junk row is the smaller half of
this bug.

**`retrieve_content` has no `is_published` check** (`feed_impl.py`), unlike the
answer branch beside it. Not reachable anonymously today: article activities
carry `site_id=None` and the public RSS path filters by site, leaving only the
passcode-gated `all_sites` tool. Latent, and cheap to close while 3b-2 is
already in this file's blast radius.

**Widening the feed audience needs a type change.** `EventPolicy.feed_audience`
is a single `Optional[Audience]`. Reaching followers *and* column subscribers
makes it a tuple, which touches every policy row, `distribute`, and the check
script — the only part of 3b with real surface area.

## Implementation notes

Found while building 3a. Recorded because each one cost real digging and would
otherwise have to be rediscovered.

**A `sinks` argument turned out to be necessary — used four times.** The plan
assumed one verb reaches one set of sinks. It does not: the same verb reaches
*different* sinks from different callers, so `distribute` takes a keyword-only
`sinks` to narrow the destinations.

| Site | Why |
|---|---|
| `postprocess_comment_update` | Sharing an existing comment to the timeline writes an Activity but must not re-notify the author, who was notified at creation. |
| `postprocess_updated_article` | Has never fanned out or notified; widening it would not be neutral. |
| `articles.create_article` | Same — the crud-level write had neither. |
| `me.follow_user` | Notification is unconditional, Activity only on a *new* follow. Two calls. |

Three of the four are `create_article`/comment duplication, i.e. the escape
hatch is mostly compensating for the bugs 3b removes. Worth re-checking after
3b whether it can be deleted.

**`follow_user` does not collapse to a single call**, contrary to the plan
above. `upvote_answer` does — both its sinks share the `not upvoted_before`
condition. `follow_user`'s do not: the notification fires even when re-following
someone you already follow, while the Activity does not.

**The policy table was missing the notification exclusions.** It recorded v1's
unapplied feed exclusions but not the `author_id != receiver_id` guards the
notification call sites actually apply. Added as `notify_exclusions`, in force
for eight verbs: `answer_question`, the four `comment_*`, `reply_comment`,
`edit_question`, `create_message`.

**Timestamps.** `Activity.created_at == event.created_at` at every existing
call site, so `distribute` derives it. `Notification.created_at` is *not* the
event's — `create_with_content` has always used wall-clock, and the unread list
sorts by it, so that behavior is preserved deliberately.

**Derivations that turned out to be available.** All four upvote services
already compute `upvoted_before` before calling crud, so the relocation is
clean. `Comment.shared_to_timeline` is persisted, so the Activity precondition
for comments is derived rather than passed.

**`crud_notification.create_with_content` was deleted outright.** Once
`notify_mentioned_users` used `events.notify_users` it had no callers, and the
standing `FIXME crud layer should not call higher level components` went with
it.

**`crud_activity.py` went too — all of it.** Not anticipated by the plan:
`distribute` builds the `Activity` itself, which left all nine factories dead,
and the module's only other callers were three readers used exclusively by
`tests/app/crud/a/test_crud_activity.py`. Module and test file both deleted
(202 + 330 lines).

**`postprocess_updated_article` needs converting** from `execute_with_db` to
`execute_with_broker`, since `distribute` takes a `RequestContext`.

## Also folded in (done in #167)

`activity_policy.POLICY` still listed `emitted_by` for
`accept_submission_suggestion` and `accept_answer_suggest_edit` after #166
removed the dead event construction from both. Both are now `emitted_by=()`
with a "no live emitter" note, alongside the other four. Descriptive only; no
behavior depended on it.

## Deferred to step 4

- Activity/Feed responsibility reassignment: Activity as the complete,
  deduplicated event log and the source for subject queries; Feed as a pure
  receiver index with `subject_user_uuid` dropped.
- Fan-out-on-write vs resolving the audience at read time. Kept decidable by
  keeping fan-out behind the single `deliver(activity, audience)` call.
- The outbox question — constructing the event at the moment of occurrence
  rather than in phase 2, which would fix both the timestamp skew and events
  being lost if the process dies before the background task runs.
- Tier 3 renames (model, schema and table names), which stay blocked until the
  above settles what the right names are.
