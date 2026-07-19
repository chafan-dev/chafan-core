# 16: Measurement Infrastructure Needed (Cache Hit/Miss + SQL Query Count)

**Phase:** 3 — Big refactors | **Effort:** Unscoped (placeholder) | **Risk:** N/A until built

**Status:** Documents a known gap. No implementation committed.

---

## What this proposal is

A placeholder. `13-cache-scope-reduction.md` and `14-n-plus-one-with-link-preview.md` both state "measure before optimizing" as their core method. Neither can do that today because the measurement tools don't exist. This proposal records the need so future work doesn't quietly skip measurement.

## What we need

Two thin instrumentation layers, both as FastAPI middleware:

### A. Per-request SQL query counter

For each request, count:
- Total SQL statements executed.
- Optionally: per-table breakdown.
- Attributed to the endpoint (path + method).

Output: a log line via `chafan.measurement` (or extend the existing `chafan.request` line from `10-request-logging.md`) with the count. Aggregating by endpoint over a sample window gives the N+1 hot list.

Implementation sketch (not committed): SQLAlchemy `before_cursor_execute` event hook incrementing a contextvar counter, flushed at request end.

### B. Per-request cache hit/miss sampler

For each Redis cache `get`, record hit or miss with the key prefix. Per-request totals plus per-prefix totals over a sample window tell us:
- Which cache prefixes have meaningful hit rates (keep them).
- Which prefixes are near-zero hits (delete them — `13-cache-scope-reduction.md` Part A).

Implementation sketch (not committed): wrap the Redis client used by `cached_layer.py` with a thin recorder.

## Why deferred (not built now)

- The measurement tools themselves are simple, but deciding the output format, sampling strategy (every request? 1%? specific endpoints?), and storage (logs vs. Prometheus vs. a Redis sorted set) needs concrete answers before building.
- v2's `10-request-logging.md` lands a logging baseline first. Measurement can ride on the same logger config rather than inventing parallel infra.
- No proposal in v2 needs measurement before Phase 3. Building it earlier would just produce data nobody reads.

## How `13` and `14` should treat this

Both proposals' "measure first" steps depend on measurement. **Prefer** to have this infra built first; if it isn't, the proposal owner ships a minimum-viable measurement for the specific change at hand.

Concretely:

- `13` removing a cache prefix: **prefer** at least one week of hit/miss data for that prefix. Minimum-viable: a scoped log-wrap for just the prefixes being touched, measured for a few days, recorded in the PR description. Don't let "the big infra isn't built" block a small, well-reasoned change.
- `14` adding eager loading to a CRUD method: **prefer** the per-request query counter middleware. Minimum-viable: `SQLALCHEMY_ECHO=true` in a dev run against representative data, with before/after query counts pasted into the PR description.

The minimum-viable version creates throwaway code, which is acceptable. Escalate to the full infra if the pattern keeps repeating — but an N+1 fix on one endpoint shouldn't wait on a project-wide measurement framework.

What to avoid: shipping the change with **no** measurement at all. "Measure before optimizing" exists because cache and N+1 fixes regularly make things worse without it. A short log-wrap or `SQLALCHEMY_ECHO` run is enough — just don't ship blind.

## Triggers for actually building this

- `13-cache-scope-reduction.md` is ready to start its measurement phase.
- `14-n-plus-one-with-link-preview.md` is ready to start its per-resource baseline pass.
- Whichever comes first owns building the minimum viable version of this measurement infra.

## Acceptance (when eventually built)

- Per-request query count visible in logs for at least a sample of requests.
- Per-request cache hit/miss visible in logs for at least a sample of requests.
- Aggregation over a sample window can produce: top-N endpoints by query count, top-N cache prefixes by hit rate.
- No measurable latency regression from the instrumentation itself (verify before enabling in prod).

## Related

- `10-request-logging.md` — the logger conventions this would build on.
- `13-cache-scope-reduction.md` — depends on this for cache hit/miss data.
- `14-n-plus-one-with-link-preview.md` — depends on this for query counts.
