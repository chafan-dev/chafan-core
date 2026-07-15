# Target Architecture — Working Draft

**Status:** draft for discussion | **Date:** 2026-07-15

Two parts: (1) the ideal structure of chafan-core, (2) the implementation plan to get there.

Relationship to `chafan_backend_improve_v2/`: this draft does not replace the v2 proposals. It gives them a structural destination. Where a step below overlaps a v2 proposal, the proposal is referenced and stays the source of truth for its own details.

---

# Part 1 — Ideal structure

## 1.1 Design decisions this structure encodes

These were settled during the 2026-07 architecture review; they are inputs, not open questions:

- **D1. Caching is not a layer.** The Redis-cache-over-SQL design was an AWS-era cost optimization (pre-2022, pay-per-query RDS). Postgres is now on-prem, cheap, and fast. Redis remains for genuinely ephemeral state (login OTP, view-bump queue, ws queues) and for the small set of heavy materialized payloads defined by proposal 13.
- **D2. No visitor/user schema split.** The `X` vs `XForVisitor` family is dropped. A page is either publicly available or requires an authenticated + authorized user. One schema per resource.
- **D3. Private sites exist in prod.** They are being sunset, but no code may assume all sites are public. Site-membership checks stay load-bearing.
- **D4. Background work is best-effort.** Task failures are logged (Sentry), never retried, never surfaced to users. This is the accepted bar; the infrastructure should be no heavier than the guarantee.
- **D5. One process in prod** (single uvicorn, no `--workers`). In-process scheduling is safe. Revisit only if we ever scale out.
- **D6. No read replica.** Nobody knows why `ReadSessionLocal` exists; there is one Postgres instance. Delete the concept.

## 1.2 The five levels

```
┌────────────────────────────────────────────────────────┐
│ 1. api/          HTTP: routing, auth deps, rate limit  │
│                  parse request → call service → schema │
├────────────────────────────────────────────────────────┤
│ 2. services/     business logic, one module per domain │
│                  permissions, orchestration, events,   │
│                  cache decisions, background side      │
│                  effects                               │
├────────────────────────────────────────────────────────┤
│ 3. responders/   ORM → API schema shaping (read-only)  │
├────────────────────────────────────────────────────────┤
│ 4. crud/         DB queries, plain functions           │
├────────────────────────────────────────────────────────┤
│ 5. infra         RequestContext (db+redis+principal),  │
│                  cache.py, email/, aws.py, mq.py,      │
│                  scheduler                             │
└────────────────────────────────────────────────────────┘
```

**The one structural rule: imports point downward only.** Level N may import N+1 and below, never sideways into another level-2 domain's internals (use its public service functions), never upward. This is the rule that dissolves today's circular-import cluster (`cached_layer ↔ materialize ↔ feed ↔ view_counters`).

### Level 1 — `api/endpoints/`

- Parses/validates the request, resolves auth via `deps.py`, calls **one** service function, returns its schema.
- May import: `services/`, `schemas/`, `deps`.
- May NOT import: `crud`, `responders`, `models` internals, redis, or reach through objects (`x.materializer.y`).
- Today all 32 endpoint files import `crud` directly and 28 reach into `cached_layer.materializer.*`. That traffic all moves behind service functions.

### Level 2 — `services/`

One module per domain: `services/questions.py`, `answers.py`, `sites.py`, `comments.py`, `users.py`, `notifications.py`, `reputation.py` (= today's `rep_manager.py`, which is the proven template), `feed.py`, `search.py`, `viewcounts.py`.

A service function owns the whole use case:

1. permission check (via `user_permission.py`)
2. reads/writes via `crud/`
3. transaction boundary (services commit; nothing below them does)
4. cache get-or-set decisions (via `infra/cache.py`) for the few payloads that stay cached
5. event/notification/webhook side effects — scheduled as post-response background work, not awaited
6. shape the return value via `responders/`

`user_permission.py` is the single home for access predicates (`question_read_allowed`, `user_in_site`, ...). Services call it; responders never do.

### Level 3 — `responders/`

- Pure shaping: ORM object in, Pydantic schema out. The caller has already decided the principal may see this object.
- Allowed a db handle for cheap child lookups during shaping, but no permission logic, no redis, no mutation.
- One responder per resource (D2 kills the `*ForVisitor` twins).
- Absorbs everything worth keeping from `materialize.py`, then materialize dies.

### Level 4 — `crud/`

- Plain query functions per domain: `get_by_uuid(db, uuid)`, `get_all_public_readable(db)`, etc.
- The generic `CRUDBase` is deleted (FastAPI-template legacy; its `dict|schema` update gymnastics and generics buy nothing at this scale). Existing call sites keep working during migration by keeping module/function names stable.
- No commits (services own transactions), no redis, no schema shaping.

### Level 5 — infra

- **`RequestContext`** (~50 lines): lazy db session + lazy redis + `principal_id` + `try_get_current_user()`. This is `DataBroker` and the rump of `CachedLayer` merged into one class. Constructed per-request by `deps.py`, passed down into services.
- **`cache.py`**: `get_or_set(redis, key, type_, fetch, ttl)` plus the version-key invalidation scheme from proposal 13. A utility that services call — not a place code lives.
- **`scheduler.py`**: the APScheduler instance and its job registrations, moved out of `main.py`.
- External clients: `email/`, `aws.py`, `mq.py` (ws push), outbound HTTP (link preview fetch).

### Background work (crosses levels 2 and 5)

Two mechanisms only, both already in the codebase's vocabulary:

1. **Post-response side effects**: FastAPI `BackgroundTasks` calling plain service functions. Replaces all 17 Dramatiq actors (see D4 — Dramatiq's retry/durability is already neutralized by `execute_with_broker` swallowing every exception, so it currently provides only "run elsewhere" at the price of a separate worker process that fails silently).
2. **Periodic/batched work**: APScheduler interval jobs. For deferred batching, the existing Redis-list + interval-drain pattern (view counts) is the house queue.

## 1.3 Worked example — the write path (create answer)

Where does a write happen? Split across two levels: **crud owns the SQL statement, the service owns the use case and the transaction.** Endpoints and responders never write.

```
POST /answers/                       api/endpoints/answers.py
  └─> services/answers.create_answer(ctx, answer_in, background_tasks)
        1. audit log                 crud.audit_log.create(...)
        2. fetch target              crud.question.get_by_uuid(db, ...)
        3. permission                user_permission.check_can_write_answer(db, user, question.site)
        4. business rules            writing-session check; "one answer per user per question"
        5. write                     crud.answer.create_with_author(db, ...)   ← db.add()/flush(), NO commit
        6. commit                    ctx.db.commit()                           ← the one transaction boundary
        7. side effects              background_tasks.add_task(services.answers.postprocess_new_answer, answer.id)
        8. respond                   responders.answer.answer_schema_from_orm(...)
```

The endpoint shrinks to: parse `AnswerCreate`, resolve auth deps, call `create_answer`, return the schema. (`BackgroundTasks` is request-scoped, so the endpoint injects it and passes it down — the one infra object that travels level 1 → 2.)

Today's `create_answer` endpoint already performs steps 1–8 — it is a proto-service in the wrong layer. The structural change is not new steps but two relocations:

- **The steps move from `api/` to `services/`** so HTTP concerns and business logic separate.
- **The commit moves to exactly one place.** Today a single use case commits in three: inside crud methods (`CRUDBase.create`, `create_with_author` both call `db.commit()`), inline in endpoint bodies, and implicitly in `DataBroker.close()` at request end. A multi-write use case (e.g. answer update, which inserts an `Archive` then updates the `Answer`) is therefore not atomic — a failure between commits leaves a partial write. In the target, crud does `db.add()`/`db.flush()` only, the service commits once at the end, and `RequestContext.close()` rolls back anything uncommitted instead of committing it.

Migration note: crud methods lose their internal `db.commit()` as they're demoted to plain functions (step 4 of Part 2); until a crud module is demoted, its legacy commit behavior is tolerated.

## 1.4 What ceases to exist

| Today | Fate |
|---|---|
| `cached_layer.py` (1,019 lines) | dissolved: context → `RequestContext`, caching → `cache.py`, business logic → `services/`, rec computations → `recs/` |
| `materialize.py` (1,148 lines) | dissolved per-resource into `responders/` + `user_permission.py`; `*ForVisitor` halves deleted outright (D2) |
| `data_broker.py` | merged into `RequestContext`; `use_read_replica` deleted (D6) |
| Dramatiq (broker, 17 actors' plumbing, worker screen session, nix dep) | deleted; bodies become service functions on `BackgroundTasks` |
| `task_utils.py` | deleted (already marked for removal); services own sessions/commits explicitly |
| `crud/base.py` `CRUDBase` | deleted; crud modules become plain functions |
| `schemas/*ForVisitor` + their responders/cache keys | deleted (D2) |
| `ReadSessionLocal`, `simple_session.py` | deleted (D6) |
| `task.py` (762 lines) | split: actor bodies → `services/`; `write_view_count_to_db` → `services/viewcounts.py`; `refresh_search_index` → `services/search.py` |

---

# Part 2 — Implementation plan

Ordering principle: correctness first, then deletions that shrink the surface, then the structural moves. Every step lands independently; no big-bang. Avoid DB migrations throughout (v2 principle 7) — nothing below needs one.

## Step 0 — Fix the responder permission/data stubs

**Urgency: this is a live issue, not tech debt** (D3: private sites exist).

- `responders/question.py:27-35` — `user_in_site` stub returns `True` for everyone. Route it to the real check in `user_permission.py`.
- `responders/answer.py` — `bookmarked` and `comment_writable` hardcoded `True` (data bugs); `can_read_answer` commented out; draft-body read permission unchecked (`FIXME` at line 53). Restore each: read-permission at fetch time (the established `get_question_by_uuid` → `question_read_allowed` pattern), real values for the two booleans, author-only guard on draft bodies.

Small diff, no structural change, ships first.

## Step 1 — Resume the materialize kill, per-resource

Recipe, one resource per PR (question, answer, submission, article, comment, then the small fry):

1. Move the resource's permission predicate into `user_permission.py`.
2. Call it from the endpoint/service at fetch time.
3. Port schema shaping into `responders/<resource>.py` — porting only the authenticated schema; delete the `*ForVisitor` twin (schema class, responder, cache keys) in the same PR (D2). Public pages serve the same schema behind a "public or authorized" predicate.
4. Delete the materialize version. When the last resource lands, delete `materialize.py`.

Overlaps: proposal 14's schema-collapse intent is executed here per-resource rather than as a separate pass. D2 means roughly half of materialize is deleted rather than migrated.

## Step 2 — Remove Dramatiq

1. In the 8 dispatching endpoint files, replace `run_dramatiq_task(postprocess_x, id)` with `background_tasks.add_task(postprocess_x, id)`.
2. Strip `@dramatiq.actor` decorators; drop the broker setup (`task.py:71-74`), `run_dramatiq_task` (`common.py`), `task_utils.py` (inline explicit session/commit into each function).
3. Delete `scripts/launch_serv/3_dramatiq_screen.sh` / `_dramatiq.sh`; remove `ps.dramatiq` from `flake.nix`. One fewer prod screen session.
4. Anything measured too slow for post-response execution moves to the Redis-list + APScheduler-drain pattern instead.

Caveats accepted by D4/D5: tasks die with the process (bar is already best-effort); in-process scheduling duplicates if uvicorn ever gets `--workers` (at which point the scheduler moves to a tiny standalone process — not preemptively).

Overlaps: extends proposals 04/05 (scheduled consolidation, fake-async cleanup).

## Step 3 — Cache scope reduction = CachedLayer breakup

Proposal 13 stays the source of truth for scope and invalidation design (including its Appendix A/B design-note gate). This draft reframes its execution as the structural refactor:

1. Extract `infra/cache.py` (`get_or_set` + version keys per 13C).
2. Walk `CachedLayer` method by method: simple PK/index reads lose their cache wrapper and move to services (13's "stop caching" list); heavy payloads that stay cached move to services calling `cache.py`; rec-engine computations (similarity matrices, follow-fanout, contributions) move to `recs/`; mutations (`delete_answer`, `create_site`, `try_consume_invitation_link_by_uuid`) move to their domain services; `request_text` moves next to link-preview code; `create_audit` to `services/audit.py`.
3. What remains of `CachedLayer` is broker + principal — merge with `DataBroker` into `RequestContext`, update `deps.py`, delete both old classes. Delete `ReadSessionLocal`/`use_read_replica` here (D6).
4. Remove `is_dev()` from all cache paths (13D).

Gate: proposal 13's measurement prerequisite (16-measurement-infra) applies to the *what stays cached* decision. The structural moves in (2)–(3) don't need measurement and can proceed; when in doubt whether a payload is "heavy," drop the cache — it can be re-added behind `cache.py` later with one line.

## Step 4 — Services extraction + crud demotion (opportunistic, ongoing)

No dedicated migration. Standing rule once steps 0–3 land:

- Touching an endpoint? Move its business logic into `services/<domain>.py`; the endpoint shrinks to parse → call → return.
- Touching a crud module? Replace its `CRUDBase` inheritance with plain functions; move any commits up into the calling service. Delete `crud/base.py` when the last inheritor is gone.
- New code follows the layer rules from day one.

Optional ratchet: a small import-linter check (endpoints may not import crud/responders; responders may not import services; etc.) turns the architecture from convention into a CI guarantee. Cheap to add after step 3.

## Sequencing summary

| Step | Size | Risk | Depends on |
|---|---|---|---|
| 0. Responder permission stubs | S | Low | — |
| 1. Materialize kill (per-resource, ~6 PRs) | M each | Medium | 0 |
| 2. Dramatiq removal | M | Low–Medium | — (parallel to 1) |
| 3. Cache reduction / CachedLayer breakup | L | High (proposal 13's gates apply) | mostly 1 |
| 4. Services + crud demotion | ongoing | Low | 0–3 |

## Open questions

1. `feed.py` (413 lines) mixes activity storage, feed fanout, and reading — does it become `services/feed.py` wholesale, or split (fanout is write-path, reading is query-path)? Decide when step 3 forces the import untangling.
2. Webhook delivery (`webhook_utils.py`) does outbound HTTP from the request process post-Dramatiq. Fine at current traffic; if a slow webhook endpoint ever hurts, move delivery to the Redis-drain queue. No action now.
3. Does `mq.py`/ws push survive the CachedLayer breakup unchanged, or fold into `services/notifications.py`? Small either way.
