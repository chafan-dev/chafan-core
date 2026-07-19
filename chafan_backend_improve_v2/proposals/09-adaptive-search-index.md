# 09: Adaptive Search Index Rebuild

**Phase:** 2 — Feature-level | **Effort:** 1-2 days | **Risk:** Medium

**Depends on:** `04-scheduled-consolidation.md` (APScheduler hosts the tick job).

---

## Problem

The search index (Whoosh, file-based) needs periodic rebuild. Today:

- Dev uses an `is_dev()` shortcut in `crud_question.py:53-64` and `crud_answer.py:96-107` that returns all results without actually hitting the index. Hides dev/prod divergence.
- Prod uses a time-based rebuild schedule that's either too frequent (wasted work on a quiet site) or too sparse (stale search results when activity spikes).

## Fix — adaptive rebuild via Redis point counter

Replace the `is_dev()` shortcut and the fixed rebuild schedule with a unified, adaptive mechanism driven by a Redis-backed point counter.

### Point formula

| Event | Points |
|-------|--------|
| New question | +1.0 |
| New answer | +0.5 |
| New article | +0.3 |
| 1 minute of wall-clock time | +0.01 |

Points accumulate in a Redis counter (`search_index:points`). When points exceed the threshold, trigger a full rebuild.

**Note: the formula is an initial estimate.** Review it again at implementation time — verify the coefficients against actual traffic patterns and the time-accumulation rate against how stale we can tolerate the index being during a quiet period.

### Thresholds

- Dev: threshold `10.0` (rebuild often to catch bugs).
- Prod: threshold `100.0` (tuned post-deployment based on observed activity).

Same code path; only the threshold differs, sourced from config.

### Time-based accumulation replaces the 24h floor

The v1 proposal had a "rebuild at least every 24h" safety net. Drop it:

- At 0.01 points/minute, time alone accumulates ~14.4 points/day.
- At prod threshold 100, time alone triggers a rebuild roughly every week.
- At dev threshold 10, time alone triggers a rebuild roughly once a day.

If the effective time-alone-to-threshold interval exceeds acceptable staleness, tune the per-minute coefficient **or** the threshold — not both. Keep the formula intact across environments.

### Control flow

```python
# APScheduler tick every N minutes (N small, e.g. 5)
TIME_POINTS_PER_MINUTE = 0.01
LAST_TICK_KEY = "search_index:last_tick_ts"
POINTS_KEY = "search_index:points"
LOCK_KEY = "search_index:rebuild_lock"

def search_index_tick():
    now = int(time.time())
    last_tick_ts = redis.get(LAST_TICK_KEY)
    if last_tick_ts is None:
        elapsed_minutes = 0.0  # first tick after deploy / Redis flush
    else:
        elapsed_minutes = max(0.0, (now - int(last_tick_ts)) / 60.0)
    redis.set(LAST_TICK_KEY, now)

    points = redis.incrbyfloat(POINTS_KEY, TIME_POINTS_PER_MINUTE * elapsed_minutes)
    if points < settings.SEARCH_INDEX_REBUILD_THRESHOLD:
        return

    # SET ... NX EX is atomic; setnx() in redis-py does not take ex.
    acquired = redis.set(LOCK_KEY, "1", nx=True, ex=COOLDOWN_SECONDS)
    if not acquired:
        return
    try:
        rebuild_full_index()
        redis.set(POINTS_KEY, 0)
    except Exception:
        # Do not reset points on failure; let the next tick retry.
        # Lock expires via ex=COOLDOWN_SECONDS.
        raise
```

On event (new question, new answer, new article), increment points via `redis.incrbyfloat(POINTS_KEY, EVENT_POINTS[event_type])`. Simple and race-safe via `INCRBYFLOAT`.

Notes on the gap calculation:
- Storing `last_tick_ts` in Redis (rather than computing `MINUTES_SINCE_LAST_TICK` from a fixed schedule) means a missed tick — worker restart, scheduler hiccup — still accumulates the right amount of time on the next tick.
- First-ever tick after deploy contributes zero time-points (no baseline). That's fine; events accumulate normally and the next tick has a baseline.
- If Redis is flushed, the counter resets to zero and the cycle restarts. Acceptable; worst case is a slightly stale index for one cycle.

### Locking and cooldown

- `SETNX` with a cooldown expiry prevents concurrent rebuilds if multiple tick processes exist (currently only one, but defensive).
- Cooldown = rebuild duration + safety margin. Concrete value depends on rebuild timing; measure in dev first.
- Full rebuild is preferred over incremental for simplicity. Whoosh handles full rebuild fine at current corpus size.

### Remove `is_dev()` from search

Delete the dev-bypass branches in `crud_question.py:53-64` and `crud_answer.py:96-107`. Dev uses the same Whoosh index as prod, rebuilt on the same adaptive cadence (just with a lower threshold).

## Dependencies

- **`04-scheduled-consolidation.md`** must land first so APScheduler is the scheduling backbone.
- Does **not** require `06-dev-prod-unification.md` — the dev/prod parity here is self-contained (config flag `SEARCH_INDEX_REBUILD_THRESHOLD`).

## Acceptance

- One code path for search indexing in dev and prod.
- Redis counter drives rebuilds; no fixed schedule.
- `is_dev()` removed from search CRUD files.
- Rebuild cooldown prevents rebuild-storms.
- Dev index stays fresh enough for development; prod doesn't rebuild unnecessarily.

## Verification

Instrument the rebuild trigger with a log line including:
- Trigger-time point value
- Which events contributed most (optional, useful for tuning)
- Rebuild duration

Review after a week in prod and tune threshold/formula if needed.
