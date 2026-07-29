# Target Architecture

**Status:** adopted; steps 0–3 landed, step 4 in progress | **Date:** 2026-07-15 | **Last reviewed:** 2026-07-29

Two parts: (1) the ideal structure of chafan-core, (2) the implementation plan to get there.

Relationship to `chafan_backend_improve_v2/`: this draft does not replace the v2 proposals. It gives them a structural destination. Where a step below overlaps a v2 proposal, the proposal is referenced and stays the source of truth for its own details.

## Progress at a glance (2026-07-29)

| Step | Status | Landed in |
|---|---|---|
| 0. Responder permission stubs | **done** | `18ac15d` |
| 1. Materialize kill (per-resource) | **done** | #119, #137, #143, #144, #151 + intermediate commits |
| 2. Dramatiq removal | **done** | `a5554a2`, `c04eda1`, #146 |
| 3. Cache reduction / CachedLayer breakup | **done** | #124, #125, #147, #148, #149, #153 |
| 4. Services + crud demotion | **in progress** | #155–#163; items 1, 2, 5 done — items 3, 4, 6, 7, 8 remain |

The five levels now exist as directories: `api/endpoints/` (40 files), `services/` (43 modules), `responders/` (14), `crud/` (30), and `infra/` (7). `cached_layer.py`, `materialize.py`, `data_broker.py`, `task.py`, `task_utils.py`, `simple_session.py`, `crud/base.py`, `app/search.py`, `app/view_counters.py`, the Dramatiq broker and its 17 actors, `ReadSessionLocal`/`use_read_replica`, and the `*ForVisitor` schema family are all deleted. Both ratchets (`check_layer_imports.py`, `check_service_commits.py`) run in CI and are green.

**Both ratchet allowlists are now empty**, and `§1.3`'s single-transaction-boundary rule holds globally: `api/`, `services/` and `crud/` contain zero `db.commit()` calls. The only commit is the one in `api/deps.py` at request end.

**`CRUDBase` is gone** (#160): all 30 crud modules are plain functions, zero classes remain in `crud/`, and no crud module commits.

What is *not* yet true: both `RequestContext` (193 lines) and `PrincipalView` (233) are larger than their target shape, the ratchet has not been widened beyond its original four rules, and naming residue from the dissolved modules is still visible throughout. Details in step 4.

**Caveat for readers and for anyone briefing an agent from this document:** this file has drifted from the tree before, in ways that cost real time — it once named three fat endpoints when `me.py` had already been refactored, said 27 `CRUDBase` inheritors when there were 23, told a reader to create a `services/people.py` that already existed, and prescribed a destination for item 5 that would have violated the layering rules it defines. Verify each claim against the code before acting on it.

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

**The one structural rule: imports point downward only.** Level N may import N+1 and below, never sideways into another level-2 domain's internals (use its public service functions), never upward. This is the rule that dissolves the then-current circular-import cluster (`cached_layer ↔ materialize ↔ feed ↔ view_counters`) — since dissolved, and now enforced in CI by the step 4 ratchet.

### Level 1 — `api/endpoints/`

- Parses/validates the request, resolves auth via `deps.py`, calls **one** service function, returns its schema.
- May import: `services/`, `schemas/`, `deps`.
- May NOT import: `crud`, `responders`, `models` internals, redis, or reach through objects (`x.materializer.y`).
- At the time of writing, all 32 endpoint files imported `crud` directly and 28 reached into `cached_layer.materializer.*`. That traffic all moves behind service functions. *(As of 2026-07-29: **zero** of 40 endpoint files import `crud`/`responders`, the ratchet allowlist is empty, and no endpoint reaches through objects. This bullet is now enforced rather than aspirational.)*

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

| Today | Fate | Status |
|---|---|---|
| `cached_layer.py` (1,019 lines) | dissolved: context → `RequestContext`, caching → `cache.py`, business logic → `services/`, rec computations → `recs/` | **done** |
| `materialize.py` (1,148 lines) | dissolved per-resource into `responders/` + `user_permission.py`; `*ForVisitor` halves deleted outright (D2) | **done** |
| `data_broker.py` | merged into `RequestContext`; `use_read_replica` deleted (D6) | **done** |
| Dramatiq (broker, 17 actors' plumbing, worker screen session, nix dep) | deleted; bodies become service functions on `BackgroundTasks` | **done** |
| `task_utils.py` | deleted (already marked for removal); services own sessions/commits explicitly | **done** |
| `crud/base.py` `CRUDBase` | deleted; crud modules become plain functions | **done** (#160) — 29 modules converted; `crud/__init__.py` now aliases the *module* (`from . import crud_user as user`) instead of a singleton, so the `crud.<domain>.<fn>(db, ...)` call surface was preserved unedited |
| `schemas/*ForVisitor` + their responders/cache keys | deleted (D2) | **done** — schemas in #119/#151, the surviving alias methods and dual predicate in the D2 follow-up (see below) |
| `ReadSessionLocal`, `simple_session.py` | deleted (D6) | **done** |
| `task.py` (762 lines) | split: actor bodies → `services/`; `write_view_count_to_db` → `services/viewcounts.py`; `refresh_search_index` → `services/search.py` | **done** (#146) |

---

# Part 2 — Implementation plan

Ordering principle: correctness first, then deletions that shrink the surface, then the structural moves. Every step lands independently; no big-bang. Avoid DB migrations throughout (v2 principle 7) — nothing below needs one.

## Step 0 — Fix the responder permission/data stubs — **done** (`18ac15d`)

**Urgency: this is a live issue, not tech debt** (D3: private sites exist).

- `responders/question.py:27-35` — `user_in_site` stub returns `True` for everyone. Route it to the real check in `user_permission.py`.
- `responders/answer.py` — `bookmarked` and `comment_writable` hardcoded `True` (data bugs); `can_read_answer` commented out; draft-body read permission unchecked (`FIXME` at line 53). Restore each: read-permission at fetch time (the established `get_question_by_uuid` → `question_read_allowed` pattern), real values for the two booleans, author-only guard on draft bodies.

Small diff, no structural change, ships first.

## Step 1 — Resume the materialize kill, per-resource — **done**

Recipe, one resource per PR (question, answer, submission, article, comment, then the small fry):

1. Move the resource's permission predicate into `user_permission.py`.
2. Call it from the endpoint/service at fetch time.
3. Port schema shaping into `responders/<resource>.py` — porting only the authenticated schema; delete the `*ForVisitor` twin (schema class, responder, cache keys) in the same PR (D2). Public pages serve the same schema behind a "public or authorized" predicate.
4. Delete the materialize version. When the last resource lands, delete `materialize.py`.

Overlaps: proposal 14's schema-collapse intent is executed here per-resource rather than as a separate pass. D2 means roughly half of materialize is deleted rather than migrated.

**D2 completion note (2026-07-24).** Deleting the `*ForVisitor` *schemas* in #119/#151 left three kinds of residue behind, since found and removed:

- Three pass-through alias methods on `PrincipalView` (`preview_of_question_for_visitor`, `preview_of_answer_for_visitor`, `submission_for_visitor_schema_from_orm`) that only forwarded to their non-visitor counterpart. Two had no callers at all.
- `visitor_can_read_answer` in `user_permission.py` — dead once `answer_read_allowed` absorbed the anonymous case.
- One genuinely-live dual path: `responders/article.py` branched on `if principal_id:` between local `can_read_article` and `visitor_can_read_article` predicates. Both are now `user_permission.article_preview_read_allowed`, written to the same shape as `answer_read_allowed` — one predicate, anonymous handled by a branch inside it. This also removed the last permission logic from a responder body (§1.2 forbids it there).

Lesson for the remaining steps: deleting a schema twin is not the same as deleting the code path that fed it. Grep for the snake_case form (`for_visitor`) as well as the class name.

Coverage gap this exposed: every article API test creates articles with `visibility: "anyone"`, so the anonymous/non-ANYONE branch — the only case where the two old predicates disagreed — had no test. Pinned by `tests/app/test_user_permission.py`.

Known asymmetry left in place deliberately: `article_read_allowed` (full body) is *stricter* than `article_preview_read_allowed`, requiring ANYONE visibility even for authenticated non-authors. That is a payload distinction rather than a principal-type twin, so it is not a D2 violation, but it looks unintentional and is security-relevant. Worth a deliberate decision rather than a silent change.

## Step 2 — Remove Dramatiq — **done** (`a5554a2`, `c04eda1`, #146)

1. In the 8 dispatching endpoint files, replace `run_dramatiq_task(postprocess_x, id)` with `background_tasks.add_task(postprocess_x, id)`.
2. Strip `@dramatiq.actor` decorators; drop the broker setup (`task.py:71-74`), `run_dramatiq_task` (`common.py`), `task_utils.py` (inline explicit session/commit into each function).
3. Delete `scripts/launch_serv/3_dramatiq_screen.sh` / `_dramatiq.sh`; remove `ps.dramatiq` from `flake.nix`. One fewer prod screen session.
4. Anything measured too slow for post-response execution moves to the Redis-list + APScheduler-drain pattern instead.

Caveats accepted by D4/D5: tasks die with the process (bar is already best-effort); in-process scheduling duplicates if uvicorn ever gets `--workers` (at which point the scheduler moves to a tiny standalone process — not preemptively).

Overlaps: extends proposals 04/05 (scheduled consolidation, fake-async cleanup).

## Step 3 — Cache scope reduction = CachedLayer breakup — **done** (#124, #125, #147, #148, #149, #153)

Proposal 13 stays the source of truth for scope and invalidation design (including its Appendix A/B design-note gate). This draft reframes its execution as the structural refactor:

1. Extract `infra/cache.py` (`get_or_set` + version keys per 13C).
2. Walk `CachedLayer` method by method: simple PK/index reads lose their cache wrapper and move to services (13's "stop caching" list); heavy payloads that stay cached move to services calling `cache.py`; rec-engine computations (similarity matrices, follow-fanout, contributions) move to `recs/`; mutations (`delete_answer`, `create_site`, `try_consume_invitation_link_by_uuid`) move to their domain services; `request_text` moves next to link-preview code; `create_audit` to `services/audit.py`.
3. What remains of `CachedLayer` is broker + principal — merge with `DataBroker` into `RequestContext`, update `deps.py`, delete both old classes. Delete `ReadSessionLocal`/`use_read_replica` here (D6).
4. Remove `is_dev()` from all cache paths (13D).

Gate: proposal 13's measurement prerequisite (16-measurement-infra) applies to the *what stays cached* decision. The structural moves in (2)–(3) don't need measurement and can proceed; when in doubt whether a payload is "heavy," drop the cache — it can be re-added behind `cache.py` later with one line.

**Outcome (2026-07-24).** The "when in doubt, drop the cache" escape hatch got taken almost everywhere. `infra/cache.py` is 54 lines with exactly one `get_or_set` caller (`services/invitations.py`, the daily invitation-link id). The **version-key invalidation scheme from 13C was never built, because nothing left in the codebase needs it** — the content caches are gone rather than reduced, and the remaining Redis keys are ephemeral operational state (view-bump queue, OTP). Proposal 13's measurement gate (16-measurement-infra) is therefore moot as a prerequisite: there is no "what stays cached" decision outstanding.

Consequence to accept deliberately: **every content read now hits Postgres.** That was the bet in D1 (on-prem Postgres is cheap and fast). If a payload ever measures too slow, re-add it behind `cache.py` — and *that* is the point at which 13C's version keys need building, not before.

## Step 4 — Services extraction + crud demotion — **in progress**

The standing rule (unchanged):

- Touching an endpoint? Move its business logic into `services/<domain>.py`; the endpoint shrinks to parse → call → return.
- Touching a crud module? Replace its `CRUDBase` inheritance with plain functions; move any commits up into the calling service. Delete `crud/base.py` when the last inheritor is gone.
- New code follows the layer rules from day one.

Ratchet: built and running in CI as `scripts/static_analysis/check_layer_imports.py` (#148, hardened #149). It enforces four rules — no imports of deleted modules, responders ↛ services, crud ↛ services/responders/api, api ↛ crud/responders.

### Remaining work, concretely

Item numbering is kept stable across revisions so PR descriptions can cite "Step 4, item N".

1. ~~**Delete `CRUDBase`.**~~ **Done (#160).** See §1.4.

2. ~~**The fat endpoints.**~~ **Done.** `me.py` was already thin before this item was written; the doc was wrong to list it. `people.py` landed in #159, `login.py` (543 → 180 lines) in the PR that carries this edit. **Both ratchet allowlists are now empty and §1.3 holds globally.**
   - `login.py` split into `services/auth.py`, `services/accounts.py`, `services/welcome_test.py`, plus additions to `services/forms.py`, `notifications.py`, `topics.py` and `link_preview.py`.
   - Its four `db.commit()` calls are gone. Three were the last statement before a return, so no-ops; `:84` was the genuine change — it committed a `user.flags += " activated"` mutation before the audit log and token mint, so the flag now rolls back if a later step raises, which is the atomicity hole closing as intended.
   - Two constraints discovered while preserving the contract, worth knowing before touching any endpoint: **endpoint function names are baked into OpenAPI `operationId` and `Body_*` schema names**, and **`get_request_context` is what emits a route's `security` block**. Renaming a handler or swapping its dependency changes the published spec even when the path, method and response model are untouched.

3. **`RequestContext` is 193 lines, not the ~50 in §1.2.** It still carries schema-shaping and query delegation inherited from `CachedLayer`: `preview_of_user`, `preview_of_answer`, `site_schema_from_orm`, `channel_schema_from_orm`, `get_user_follows`, `get_site_by_subdomain`, `get_site_info`, `update_notification`, `get_follow_follow_fanout`, `get_user_contributions`, plus a `broker` property that returns `self`. Each uses a function-local import to dodge the cycle it would otherwise recreate — a reliable smell that the method is in the wrong layer. These should become direct service/responder calls at the call sites. (#159 removed one such delegation, `ctx.preview_of_user`, from the `people` path.)

4. **`PrincipalView` (233 lines) is level-3 work sitting in level 5.** It is a ~30-method dispatch table from ORM object to schema, i.e. exactly what `responders/` is for, but it lives in `infra/`. Either relocate it to `responders/` or let call sites hit responders directly and delete it. Note the ratchet cannot currently catch this, because `infra/` has no outbound rule. Roughly 35 files touch `principal_view`/`as_principal`, so this is the broadest remaining diff — do it as one PR, and not concurrently with item 5.

5. ~~**Root-level modules superseded but not removed.**~~ **Done (#162).** `app/view_counters.py` and `app/search.py` are deleted.

   **This item previously read "Fold each into its service." That instruction was wrong** — it would have created layering violations, because both modules are called from *below* the service layer. The destinations actually used, by caller:

   | Code | Callers | Destination |
   |---|---|---|
   | `view_counters.add_view_async` | 4 services | `services/viewcounts.py` |
   | `view_counters.get_viewcount_*` (4 fns) | 4 **responders** | **`crud/crud_viewcount.py`** — `responders ↛ services` is ratchet-enforced, but responders may call crud |
   | `view_counters.add_view` | none — dead, logs "deprecated", returns 0 | delete |
   | `app/search.py` (Whoosh index client) | 5 **crud** modules + `services/search.py` | **`infra/search_index.py`** — `crud ↛ services` is ratchet-enforced; per §1.2 it is an external client, like `email/` and `mq.py` |

   The general lesson: *where a superseded module goes is determined by its lowest-level caller, not by its name.*

6. **Naming residue from the dissolved modules.** `materialize_event` (6 hits / 4 files), `materialize_activity` (4/1), local variables named `materializer`/`mat` (4/2), and parameters still named `data_broker`/`broker` for what is now a `RequestContext` (~137 hits / 21 files). Cosmetic, but it is the last thing making the old architecture legible in the new one. **Schedule this alone and last** — it is a rename across most of `app/`, so it conflicts with every other in-flight change.

7. **Widen the ratchet. Unblocked — item 2 is done and both allowlists are empty, so this is now the next thing to do.** Add `services ↛ api`, `responders ↛ redis`, `api ↛ models`, and an outbound rule for `infra/`. Also make allowlist entries fail once empty, so they cannot silently regrow: `check_service_commits.py` already implements that rule for its own ALLOWLIST (#157); `check_layer_imports.py` does not, and its allowlist is now an empty set that nothing defends.

8. **Test the new layers.** 43 test files; only two reach into `services`/`responders`/`infra`/`user_permission` directly. Partly addressed:
   - #156 added archive-atomicity tests (rejected update must leave no orphan archive row) for **questions** and **submissions**. The case §1.3 actually names — **answer update** — is still untested, as are articles.
   - #158 added `tests/app/api/api_v1/test_me.py`, the first test file targeting a service module's permission behavior rather than an endpoint's happy path.
   - **`login.py`'s refactor found that only 3 of its 11 routes had any coverage** (`/login/access-token`, `/check-token-validity/`, `/open-account`). The other 8 — including password recovery, reset, verification codes, and the welcome-test claim — were carried across on a throwaway before/after capture harness rather than committed tests. Turning that harness into a real `test_login.py` is the highest-value piece of this item: it is the authentication surface, and it is currently unguarded against regression.

Suggested order: **7 → 3/4 → 6**, with 8 alongside whichever domain is being touched. Item 6 must be last.

### Read gates and derived schemas — a hazard worth naming (#158)

Step 0 put resource read gates inside the responders. That works as long as every read path builds the resource's full schema. It silently fails for routes that build a **small derived schema** instead.

`services/me.py`'s subscribe/bookmark routes fetched their target with a bare `crud.<resource>.get_by_uuid`, 400'd only when the row was *missing*, and returned a compact `UserXSubscription` / `UserXBookmark`. Because they never called a responder, they never reached a gate — so an authenticated non-member of a private site could subscribe to or bookmark content there and read its subscriber count back out of the response body. Live bug, not debt (D3: private sites exist in prod).

The fix (#158) added one gate helper per resource next to the existing `services.questions.get_readable_question_http`:
`services.submissions.get_readable_submission_http`, `services.answers.get_readable_answer_http`, `services.articles.get_readable_article_preview_http`.

Three things to carry forward:

- **A read gate belongs at *fetch* time, in the service, not at *shaping* time in the responder.** The responder gate is a backstop, not the primary control. Any new route that reads a resource without building its full schema must call a `get_readable_*_http` helper.
- **Denials report "doesn't exist" (400), not 403.** These gates fold in site membership and publication state, so a distinguishable status is itself a disclosure. Matching statuses is a deliberate part of the fix, not sloppiness.
- **Gate the preview, not the body, when only the preview is served.** Bookmarking an article gates on `article_preview_read_allowed`, not the stricter `article_read_allowed` — see the asymmetry flagged under step 1 and open question 1.

Topic subscriptions are deliberately left **ungated**: topics carry no site and no visibility, so there is nothing to leak. This is pinned by a test so the gates are not extended there by analogy.

## Sequencing summary

| Step | Size | Risk | Depends on | Status |
|---|---|---|---|---|
| 0. Responder permission stubs | S | Low | — | done |
| 1. Materialize kill (per-resource, ~6 PRs) | M each | Medium | 0 | done |
| 2. Dramatiq removal | M | Low–Medium | — (parallel to 1) | done |
| 3. Cache reduction / CachedLayer breakup | L | High (proposal 13's gates apply) | mostly 1 | done |
| 4. Services + crud demotion | ongoing | Low | 0–3 | in progress (items 1, 2, 5 done) |

Actual cost of steps 0–3: roughly 30 commits across PRs #119–#154, no DB migrations (v2 principle 7 held), one production behavior change caught in review (the responder permission stubs of step 0, which were a live bug rather than debt).

Step 4 so far: #155–#163, still no DB migrations. The HTTP contract has been **byte-identical across every one of them** — the published OpenAPI spec on 2026-07-29 is unchanged from 2026-07-24, which is what made it safe to move this much code without touching the front-end.

**The refactor keeps finding live bugs rather than introducing them.** Three so far, all pre-existing, none reported by a user:

1. Step 0's responder permission stubs (`user_in_site` returning `True` for everyone).
2. #158's derived-schema gate miss — see the section above.
3. `@limiter.limit("1/minute")` on `POST /password-recovery/{email}` is **inert**, because it sits *above* `@router.post` and so decorates a function the router never registered. `/send-verification-code` has the same two decorators in the opposite order and rate-limits correctly. Demonstrated with a controlled comparison in one process from one IP: password-recovery reached the handler on all four consecutive calls, send-verification-code returned 429 from the second onward. Unauthenticated password-reset email flooding against any address. Preserved verbatim by the `login.py` refactor (behavior-neutral by design) and fixed separately.

That is three for three, which is the argument for finishing this rather than stopping at "good enough" — the layering work is what makes these visible.

## Open questions — resolved

1. **`feed.py` — split, not wholesale.** Landed in #147 as `services/feed.py` (46 lines, the read entry point) over `services/feed_impl.py` (417, storage + fanout). Deliberately *not* restructured further: feed is queued for its own redesign, and this refactor should not pre-empt those decisions. Leave it alone in passing.
2. **Webhook delivery — no action taken, as predicted.** Now `services/webhook_delivery.py`; still does outbound HTTP in the request process. Fine at current traffic. The Redis-drain queue remains the answer if a slow endpoint ever hurts.
3. **`mq.py` survived unchanged** (28 lines) and did not fold into `services/notifications.py`. It reads as infra, so it stays infra. Its `data_broker` parameter name is part of item 6 above.

## New open questions

1. Should `article_read_allowed` really be stricter than `article_preview_read_allowed` (see the D2 note under step 1)? Existing prod behavior, preserved on purpose, but likely accidental. #158 now depends on the distinction being intentional — it gates bookmarks on the looser predicate — so this deserves a decision rather than continued drift.
2. `crud/crud_user.py:try_get_visitor_user` and `recs/indexing.py:compute_interesting_*_for_visitor_user` refer to a real anonymous-user DB row used as the rec index for logged-out visitors. This is unrelated to D2's schema split and is *not* residue — but the shared vocabulary invites confusion. Worth renaming to `anonymous_user` to keep "visitor" from meaning two things.
3. `services/people.py` has two calling conventions side by side: the `list_user_*` functions take `(ctx, *, uuid, ...)` while `get_followers`/`get_followed`/`get_related_users`/`preview_of_user` take a positional ORM model. #159 added to the first group and left the second alone rather than churn working code. One of them should win.
4. `GET /people/{uuid}/related/` uses `unwrap()` on a missing user, producing `AssertionError` → 500, where every other `/people/` route returns 400. Preserved by #159 so the status code would not change silently, but it looks unintended.
5. `crud_user.update` uses `exclude_none=True` where every other domain's update path uses `exclude_unset=True`. Because the old `CRUDUser.update` passed a dict to `super()`, the base's `exclude_unset` never actually applied to user updates; #160 inlined the real behavior verbatim rather than normalizing it. Normalizing would be a genuine behavior change, so it needs a decision.
6. `main-test.yml` triggers only on `pull_request` to `main` and pushes to `better_ci` — so the test suite never runs on `main` itself. Only Static Analysis and Nix build do. Intentional?
