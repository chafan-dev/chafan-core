# Glossary

**Last reviewed:** 2026-08-02

## event, activity, feed, notification

Four names for closely related things. Mixing them up is the usual source of
confusion in this area.

| Term | Stored as | How many | Answers |
|---|---|---|---|
| **Event** | JSON in an `event_json` column | one per occurrence | *what happened* |
| **Activity** | `activity` table | one per published event | *what happened, and where it may be seen* |
| **Feed** | `feed` table | N per Activity — one per recipient | *who should see it* |
| **Notification** | `notification` table | one per targeted recipient | *who must be told* |

The short version: **Activity is subject-oriented and carries the payload;
Feed is receiver-oriented and is just an index**, `(activity_id, receiver_id)`.
Notification is a directed delivery with read state, and re-serializes the
event rather than pointing at an Activity.

An event can also land in a fourth place: `CoinPayment.event_json`, where it is
the *reason* for a coin transfer rather than something anyone reads.

`EventInternal` vs `Event`: `EventInternal` holds ids and is what gets
persisted. `Event` is the materialized, permission-checked shape returned by
the API. `responders/event.materialize_event` converts one to the other.

Which of those sinks each verb actually reaches is recorded per verb in
[`chafan_core/app/services/activity_policy.py`](../chafan_core/app/services/activity_policy.py).

Two things the model does *not* currently live up to, so the names don't
mislead: an `Activity` row is not written for every event (and `create_article`
writes two or three), and `Feed` carries a `subject_user_uuid` denormalization
so profile timelines can be read from it — a subject query answered from the
receiver table.
