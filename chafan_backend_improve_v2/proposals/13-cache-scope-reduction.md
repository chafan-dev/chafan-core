# 13: Cache Scope Reduction + Invalidation Redesign

**Phase:** 3 — Big refactors | **Effort:** 1-2 weeks | **Risk:** High

---

## Problem

The current Redis cache is load-bearing for basic SQL reads. Historical reason: chafan was originally on AWS RDS where each Postgres operation incurred cost, and caching indexed single-row reads reduced the bill.

Today:
- FastAPI, Redis, and Postgres are all self-hosted.
- No pay-per-query billing model is in use.
- Caching indexed single-row reads adds complexity (invalidation, stale-data windows, cache bugs hidden in dev by `is_dev()` bypass) for no cost benefit.

Symptoms of the over-cache:
- Cache invalidation bugs are a recurring category (stale user cards, stale answer previews).
- The `cache_matrices()` function caches things that don't need caching.
- Every `_get_cached` method in `cached_layer.py` disables itself in dev via `is_dev()` — dev/prod parity violation, and the reason we don't see cache bugs locally.

## Scope of the refactor

### Part A — define the cache scope

Keep caching only for:

1. **Heavy cross-joins** — materialized payloads that would otherwise require multiple joins and post-processing (e.g. full question page with answers, comments, related sites).
2. **Aggregated computations** — e.g. trending questions, activity feeds, discovery listings.
3. **External-call results** — link previews (fetched from external URLs), site favicons.

Stop caching:

1. Single-row reads by primary key (Postgres with indexes is fast enough).
2. Simple filtered lookups that hit an index.
3. Any payload where the cost of a cache miss is a single fast SQL query.

### Part B — delete `cache_matrices()`

Most requests are handled by the CF edge cache. The in-process cache matrices add complexity without meaningful benefit once (A) is in place. Delete.

### Part C — invalidation redesign

The current invalidation is scattered: `cache_delete(...)` calls live next to the CRUD method that mutated the row. When mutations bypass the expected CRUD path (tests, admin tools, Dramatiq actors), invalidation is missed.

New approach: **version-key invalidation** for the cached materialized payloads that remain.

- Each cacheable entity (e.g. a question with id=N) has a version key in Redis: `question:N:version` → integer.
- Cache key includes the version: `question:N:v{version}:materialized`.
- On any mutation of the question or its dependencies, increment the version key. The cached entry becomes unreachable; it'll expire naturally.
- No explicit deletes; no race conditions between write-then-invalidate.

For payloads with multiple dependencies (e.g. a question page that depends on the question AND its answers), the cache key includes all relevant version keys.

### Part D — remove `is_dev()` from caching

Once the scope is small (Part A) and invalidation is robust (Part C), dev runs the same cache path as prod. Cache bugs become visible in dev.

The `is_dev()` bypass in `cached_layer.py` (lines 114-119, 136-141, 247-250, 304-305, 321-322, 367-371, 474, 643) and `discovery.py` (47-50, 111-114) is deleted.

## Dependencies

- Must land **before** `14-n-plus-one-with-link-preview.md`. The Link Preview backend work in v1 proposes collapsing `*ForVisitor` schemas and their cache keys; that only makes sense after the cache scope is defined.
- Must land **before** `15-image-upload-r2.md`? No — image upload bypasses backend cache (CF handles edge cache, content-addressed keys mean no invalidation). Independent.
- Benefits from `10-request-logging.md` being in place — `chafan.cache` logger helps during the shrink rollout to confirm hit rates on the retained cache scope.

## Approach

1. **Measure first.** Instrument cache hit/miss per key prefix via a one-week logging pass. Keys with near-zero hits or trivial cache-miss cost are candidates for removal. The measurement tool itself does not exist yet — see `16-measurement-infra-needed.md`. This proposal cannot start its measurement phase until that tool is built.
2. Remove caching from simple PK reads (the easy wins).
3. Delete `cache_matrices()`.
4. Implement version-key invalidation for the remaining cached payloads.
5. Remove `is_dev()` from `cached_layer.py` and `discovery.py`.
6. Run for at least a week with the new setup; monitor error rates, latency, Redis memory, Postgres query volume.

## Acceptance

- Cache key count in prod drops substantially (specific target TBD after measurement).
- Redis memory footprint drops **if** the TTL/LRU decision in Appendix A lands on an eviction path that reclaims orphaned versions faster than new versions are written. If the implementer picks a strategy that leans on LRU pressure without TTLs, steady-state memory may not drop meaningfully; that's acceptable, but don't claim it as a win.
- Postgres query volume rises modestly (expected — not all cached queries were load-bearing).
- Dev and prod run identical cache code paths.
- `is_dev()` removed from all caching code.
- No new invalidation bugs introduced (monitor via Sentry + error logs).

## Risks

- **Latency regression on unprofiled hot paths.** Mitigation: week-long measurement phase before removing.
- **Redis memory spike during version-key migration.** Mitigation: roll out to one entity type at a time.
- **CF edge cache dependency.** If CF is down or rules change, backend load spikes. This is a known operational dependency and mostly out of scope for this proposal — but worth confirming CF has an appropriate fallback before going live.

## Related

- v1 Proposal 07 A1 ("enable cache in dev") is subsumed by this proposal's Part D.
- `LINK_PREVIEW_FIX_PLAN.md` backend steps B1-B12 collapse the `*ForVisitor` schema family and their cache keys. That work happens in `14-n-plus-one-with-link-preview.md` after this proposal lands.

---

## Appendix: Open questions for the implementer

Two risks in the version-key invalidation design (Part C) that are not resolved by this proposal. **Pause and discuss before building.**

### A. Memory bloat from orphaned versions

Bumping `question:N:version` does not delete the previous `question:N:v{old}:materialized` entry. The old entry stays in Redis until LRU eviction kicks in. For a busy entity with frequent mutations, many old versions can stack up.

The "Redis memory drops" claim under Acceptance is therefore not automatic — it depends on LRU evicting the old entries faster than new versions are written.

Things to discuss before building:
- Set a TTL on every cached payload (e.g. 1h–24h depending on freshness needs). Old versions then self-expire on a known timeline rather than depending on LRU pressure.
- Or: rely on Redis `maxmemory-policy=allkeys-lru` and accept the memory headroom cost.
- Or: bump to a small generation counter scheme that explicitly deletes the previous version on bump (more complex, race-prone).

### B. Multi-dep cache keys cost N round-trips

For a cached payload that depends on multiple entities (e.g. a question page depending on the question + its answers + author + site), the cache key includes all relevant version keys. Constructing the lookup key requires reading each version key first.

For a single-dep entry, the lookup is one `GET version` + one `GET payload` = 2 round-trips. For a 5-dep entry, it's 6 round-trips (or one `MGET`). For a payload that would otherwise be a single indexed Postgres query, the cache lookup can be slower than the query it's avoiding.

Things to discuss before building:
- Use `MGET` to batch the version reads (one round-trip regardless of dep count). Still N reads worth of latency on the Redis side, but no per-dep round-trip cost.
- Cap the number of deps a cache entry may have. If a payload needs more than e.g. 3 deps, don't cache it — let it be a direct query.
- Or: collapse multi-dep entries into a single coarser version key (e.g. `site:N:version` bumped on any change to site or its content). Loses precision; broader cache invalidation but faster lookups.
- Measure (per `16-measurement-infra-needed.md`) before committing to a pattern.

### Action

Before writing the version-key code, the implementer must produce a short design note answering both A and B with concrete choices. The note can live at the top of the resulting PR. Do not skip this; both risks have made cache rewrites worse-than-baseline before.
