# Scheduler Status Quo

**Purpose:** Snapshot of the current state of scheduled/periodic jobs in chafan-core as of 2026-04-19. Referenced by `proposals/04-scheduled-consolidation.md` and anything else that touches scheduling (e.g. `proposals/09-adaptive-search-index.md`, `proposals/15-image-upload-r2.md`).

Frozen in time: read the current code before trusting this file.

---

## TL;DR

1. **APScheduler is already wired up** in `main.py` and runs in-process on the FastAPI app. It currently runs exactly two jobs.
2. **Dokku cron is dead.** `app.json` still lists four cron entries pointing at `scripts/schedule-runner.py`, but nothing invokes them and the runner itself no longer imports cleanly.
3. **`scripts/schedule-runner.py` is broken.** Line 23 imports `chafan_core.scheduled.refresh_search_index`, which does not exist — the function lives in `chafan_core.app.task`. Any `python scripts/schedule-runner.py ...` invocation raises ImportError before doing anything.
4. **Dramatiq is separate.** 17 `@dramatiq.actor` functions in `chafan_core/app/task.py` run in worker processes, not in APScheduler. Do not conflate "scheduled" with "background" — they are two different systems.

---

## APScheduler — what runs today

Wiring: `chafan-core/chafan_core/app/main.py:31-34, 124-138`.

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
scheduler = BackgroundScheduler()
...
@app.on_event("startup")
def set_up_scheduled_tasks():
    scheduler.add_job(
        write_view_count_to_db,
        trigger=IntervalTrigger(minutes=settings.SCHEDULED_TASK_UPDATE_VIEW_COUNT_MINUTES),
        name="write_new_activities_to_feeds")
    scheduler.add_job(
        refresh_search_index,
        trigger=IntervalTrigger(hours=settings.SCHEDULED_TASK_REFRESH_SEARCH_INDEX_HOURS),
        name="refresh_search_index")
    scheduler.start()
```

Config defaults in `app/config.py:93-94`:
- `SCHEDULED_TASK_UPDATE_VIEW_COUNT_MINUTES = 5`
- `SCHEDULED_TASK_REFRESH_SEARCH_INDEX_HOURS = 24`

Both jobs live in `chafan_core/app/task.py`:
- `write_view_count_to_db` — `task.py:667`
- `refresh_search_index` — `task.py:715`

Note: the job registered as `"write_new_activities_to_feeds"` actually calls `write_view_count_to_db`. The display name is a leftover from an earlier design and should be renamed in `04`.

---

## Dokku cron — what's listed but dead

`chafan-core/app.json` — 4 entries:

| Schedule | Command | Currently functional? |
|----------|---------|-----------------------|
| `*/30 * * * *` | `python scripts/schedule-runner.py cache_new_activity_to_feeds` | No — runner import fails |
| `@daily` | `python scripts/schedule-runner.py daily` | No — runner import fails |
| `@weekly` | `python scripts/schedule-runner.py refresh_search_index` | No (+ duplicates APScheduler job) |
| `@weekly` | `python scripts/schedule-runner.py run_deliver_notification_task` | No — runner import fails |

Nothing is invoking these entries anymore; Dokku staging was decommissioned.

---

## `scripts/schedule-runner.py` — state

- File header carries `# TODO Remove this file. 2025-07-18`.
- Broken as of current HEAD: `from chafan_core.scheduled.refresh_search_index import refresh_search_index` at line 23 fails because `chafan_core/scheduled/` contains only `__init__.py`, `deliver_notifications.py`, `lib.py`.
- Deletion is owned by `proposals/01-makefile-cleanup.md` step 5.

Task branches in the runner (for inventory — do not try to "preserve" their behavior, most are already mirrored elsewhere):

| Task branch | Does | Current state elsewhere |
|-------------|------|-------------------------|
| `cache_new_activity_to_feeds` | `cache_new_activity_to_feeds()` + `cache_matrices()` | Both functions still exist; neither is invoked on any schedule today |
| `daily` | `fill_missing_keywords_task()` + `refresh_karmas()` | Both functions exist; neither runs on any schedule today |
| `refresh_search_index` | `refresh_search_index()` | Already runs under APScheduler every 24h |
| `run_deliver_notification_task` | `run_deliver_notification_task()` | Exists in `chafan_core/scheduled/deliver_notifications.py`; not scheduled |
| `force_refresh_all_index` | Ad-hoc admin tool, not cron | One-shot; not a scheduled job |

---

## Migration target (what `04` is actually doing)

Proposal 04 is **not** "introduce APScheduler" — APScheduler is already here. It is "migrate the remaining Dokku cron entries into the existing APScheduler, delete the runner, delete `app.json`."

Jobs to add to APScheduler (target end state):
- `cache_new_activity_to_feeds` — every 30 min (migrate from Dokku)
- `fill_missing_keywords_task` — daily (migrate from Dokku)
- `refresh_karmas` — daily (migrate from Dokku; body rewritten by `08`)
- `run_deliver_notification_task` — weekly (migrate from Dokku)

Jobs intentionally **not** migrated:
- `cache_matrices` — skipped for now; it was paired with `cache_new_activity_to_feeds` in the runner, but its scheduling fate depends on `13-cache-scope-reduction`. Revisit there.

Jobs already running (no change):
- `write_view_count_to_db` — keep (rename job display name)
- `refresh_search_index` — keep (body will be modified by `09-adaptive-search-index`)

Config: cron expressions live in code (per `04` Decisions), with the interval/cron minutes/hours surfaced as `SCHEDULED_TASK_*` settings when the default is likely to be tuned.

---

## Dramatiq (parallel system — do not touch)

17 `@dramatiq.actor` functions in `chafan_core/app/task.py` (lines 149–585). These are event-driven (fan-out on user actions), not time-driven, and run in the `worker` dyno/process. They are **not** in scope for `04` or any other scheduler proposal.

---

## What this file is NOT

- Not a design doc — see the proposals for decisions.
- Not authoritative for future state — it reflects HEAD at the date above.
- Not a place to document Dramatiq actors; they have their own lifecycle.
