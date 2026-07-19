# Deferred: Full Async Migration

**Source:** v1 `proposals/12-async-migration.md` Part A.

**Status:** Decision pending until v2 is complete.

---

## Summary of the proposal

Migrate the entire backend from sync Python (psycopg2, `requests`, sync Redis) to async (asyncpg, httpx, redis.asyncio). Gradual phased migration over months:

1. Add async engine + session alongside sync.
2. Create `AsyncCRUDBase` alongside `CRUDBase`.
3. Migrate endpoints by domain (notifications → search → feed → Q&A → users).
4. Migrate external clients (requests → httpx, redis sync → redis.asyncio).

## Why deferred

No concrete driver has been identified. Before committing to months of high-risk, high-churn work, answer:

- Is the app actually I/O-bound in prod?
- What's current p95/p99 latency, and how much of it is Python awaiting I/O vs. waiting on the DB itself?
- Is there a specific feature (long-polling, SSE, websockets, fan-out HTTP calls) that sync can't serve?
- How many concurrent requests does a single worker need to handle? If low and horizontally scalable, sync-in-threadpool is fine indefinitely.

`05-fake-async-cleanup.md` already captures most of the cleanup value (misleading `async` keywords, fire-and-forget `create_task`, `asyncio.run` in sync code) without changing the execution model. That's shipping as part of v2.

## Trigger for revisiting

- Measurement shows a specific endpoint is bottlenecked on Python-side await time (not DB time).
- A new feature genuinely requires async (persistent websocket, SSE for notifications, large fan-out).
- If any of those trigger: migrate just that endpoint as an async island. Do not kick off a whole-codebase migration.

## Decision point

Revisit after v2 completes. Three options on the table at that point:

1. **Full sync.** Stay sync, never migrate. Valid choice if the app remains request-response CRUD with acceptable latency.
2. **Full async.** Commit to the migration per v1 Proposal 12A.
3. **Async islands.** Convert specific endpoints only, keep the rest sync.

The right choice will be obvious at that point based on observed bottlenecks.
