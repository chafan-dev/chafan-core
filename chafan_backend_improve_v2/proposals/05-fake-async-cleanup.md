# 05: Fake Async Cleanup

**Phase:** 1 — Code correctness | **Effort:** 1-2 days | **Risk:** Medium

---

## Problem

The codebase contains "fake async" — code that looks async but doesn't buy any concurrency:

- Handlers declared `async def` that make only sync calls (DB, HTTP via `requests`, Redis sync client).
- `asyncio.create_task(...)` used as fire-and-forget where the task immediately blocks on sync work — effectively a no-op, and swallows exceptions.
- `asyncio.run(...)` called inside sync code to "use" async APIs, defeating the purpose and creating a new event loop per call.

These patterns are code smells at best and latent correctness bugs at worst (exceptions swallowed, event-loop interactions, ordering assumptions).

## Fix

Audit and clean up each pattern:

1. **`async def` with no awaitables.** Convert to `def` if nothing awaits inside. (FastAPI handlers: dropping `async` is safe; FastAPI runs sync handlers in a threadpool.)
2. **`asyncio.create_task` fire-and-forget in sync context.** Replace with a direct call, a Dramatiq task, or a background thread as appropriate. Fire-and-forget in a request handler is almost always wrong — exceptions never surface.
3. **`asyncio.run` inside sync code.** Either make the whole path sync (usually correct) or push the caller to be async.

## Scope — what this is NOT

- Not a migration to real async (deferred; see `deferred/async-migration.md`).
- Not a change to the DB driver or HTTP client.
- Not a change to Dramatiq workers.

This proposal only removes the misleading keywords and dangerous fire-and-forget patterns. The execution model stays sync.

## Approach

1. Grep for `async def` and audit each. For handlers with no awaits, convert to `def`.
2. Grep for `asyncio.create_task` and `asyncio.run`. Eliminate each — the replacement depends on context.
3. After each cleanup, run the full test suite and hit the affected endpoints manually.

## Acceptance

- No `async def` without at least one `await` inside (except FastAPI endpoint adapters that must be async for framework reasons — none known today).
- No `asyncio.create_task` used as fire-and-forget.
- No `asyncio.run` in sync code.

## Why this matters before `deferred/async-migration.md` is revisited

Cleaning these up first means that when (if) we later decide to go async, we start from an honest baseline. No hidden `asyncio.run` calls to discover mid-migration.
