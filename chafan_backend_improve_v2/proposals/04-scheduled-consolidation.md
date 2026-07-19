# 04: Scheduled Task Consolidation — Migrate Dokku Cron into Existing APScheduler

**Phase:** 0 — Quick wins | **Effort:** Half day | **Risk:** Low

**Source plan:** `/var/home/lizhenbo/src/chafan/glistening-soaring-hamming.md`
**Status quo reference:** `../knowledge/scheduler-status-quo.md` (read this first)

---

## Problem

Two scheduling systems exist side-by-side and one is broken:

1. **APScheduler** is already wired up in `chafan_core/app/main.py:31-34, 124-138`. It runs two jobs — `write_view_count_to_db` (every 5 min) and `refresh_search_index` (every 24 h).
2. **Dokku cron** lives in `chafan-core/app.json` (4 entries invoking `scripts/schedule-runner.py`) and is dead — the Dokku staging flow is decommissioned, and the runner itself no longer imports cleanly (`schedule-runner.py:23` tries to import `chafan_core.scheduled.refresh_search_index`, which does not exist — the function is in `chafan_core.app.task`).

Net effect: four jobs that used to run on Dokku are not running anywhere today.

Jobs that should be running (but aren't):
- `cache_new_activity_to_feeds` — previously every 30 min
- `fill_missing_keywords_task` — previously daily
- `refresh_karmas` — previously daily (body will be rewritten by `08-rep-manager-centralization.md`)
- `run_deliver_notification_task` — previously weekly

See `../knowledge/scheduler-status-quo.md` for the full inventory and current-state mapping.

## Fix

Migrate the four orphaned jobs into the existing APScheduler instance. No new scheduling infrastructure — APScheduler is already running.

1. In `main.py`'s `set_up_scheduled_tasks`, add four more `scheduler.add_job(...)` calls:
   - `cache_new_activity_to_feeds` every 30 min
   - `fill_missing_keywords_task` daily
   - `refresh_karmas` daily (current body; `08` rewrites later)
   - `run_deliver_notification_task` weekly
2. Rename the existing `write_view_count_to_db` job's display name from `"write_new_activities_to_feeds"` (stale leftover) to `"write_view_count_to_db"` so the log name matches the function.
3. Deletion of `scripts/schedule-runner.py` and `app.json` is owned by `01-makefile-cleanup.md`. This proposal does not touch those files.

### Intentionally out of scope

- **`cache_matrices`** was paired with `cache_new_activity_to_feeds` in the runner but its scheduling fate depends on the cache scope decisions in `13-cache-scope-reduction.md`. Leave it unscheduled for now; revisit in `13`. It will be a function-call orphan in the meantime — acceptable.
- **Dramatiq actors.** `chafan_core/app/task.py` has 17 `@dramatiq.actor` functions; they run in worker processes on event triggers, not on a schedule. Not in scope here.
- **`force_refresh_all_index`** branch of the runner — that was an ad-hoc admin tool, not a scheduled job. If still needed, re-expose via an admin endpoint or management command; not a cron concern.

## Forward references

- **Phase 1 (`08-rep-manager-centralization.md`)** rewrites the body of `refresh_karmas` from "batch-compute-authoritative" to "reconciliation-with-drift-logging." No conflict: this proposal wires the job slot; `08` changes what runs inside.
- **Phase 2 (`09-adaptive-search-index.md`)** changes how `refresh_search_index` decides whether to do a full rebuild. Same pattern — this proposal owns the schedule; `09` owns the body.
- **Phase 4 (`15-image-upload-r2.md`)** — if we ever add an upload canary job (currently parked in `../deferred/upload-cost-containment.md`), it registers against this same APScheduler instance.

## Decisions

- **Single APScheduler instance in the main FastAPI process.** Already the case; do not split.
- **Dramatiq continues to run in separate worker processes.** Untouched.
- **Cron expressions defined in code**, not in a config file. Where the interval is likely to be tuned, surface it as a `SCHEDULED_TASK_*` setting (matching the existing pattern in `app/config.py:93-94`).
- **No wrapper around `scheduler.add_job`.** Six direct calls is fine; an abstraction layer for six jobs is overkill.

## Acceptance

- Six scheduled jobs run via APScheduler with visible log output on app startup: `write_view_count_to_db`, `refresh_search_index`, `cache_new_activity_to_feeds`, `fill_missing_keywords_task`, `refresh_karmas`, `run_deliver_notification_task`.
- The renamed `write_view_count_to_db` job logs under its real name.
- Dev and prod run the same scheduler code path.
- Deletion of `scripts/schedule-runner.py` and `app.json` verified by `01-makefile-cleanup.md`.
