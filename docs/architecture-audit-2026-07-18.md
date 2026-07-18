# Architecture Audit — 2026-07-18

**Scope:** Compare current `dev` branch against `docs/proposals/2026-07-15-target-architecture.md`.

## Summary

The branch matches the target architecture **~85%**. Steps 0–3 are largely complete. Remaining gaps are all Step 4 (ongoing/opportunistic cleanup).

---

## What matches the design

| Proposal Item | Status |
|---------------|--------|
| 5-level structure: `api/endpoints/` → `services/` → `responders/` → `crud/` → `infra/` | Exists |
| `cached_layer.py` (was 1,019 lines) dissolved | **Deleted** |
| `materialize.py` (was 1,148 lines) dissolved | **Deleted** |
| `data_broker.py` merged into `RequestContext` | **Done** — `infra/request_context.py` (193 lines) |
| `ReadSessionLocal` deleted (D6) | **Deleted** |
| `*ForVisitor` schemas + their responders deleted (D2) | **Deleted** |
| Dramatiq removed (Step 2), replaced with `BackgroundTasks` | **Done** — 0 dramatiq references in source |
| `task.py` (app-level, was 762 lines) split into services | **Deleted** |
| `infra/cache.py` extracted | Exists (54 lines) |
| `infra/scheduler.py` (APScheduler) | Exists (60 lines) |
| `user_permission.py` as single permission hub | Exists (141 lines) |
| Services own `db.commit()` — crud only flushes | **Done** — `crud/base.py` docstring: "All mutating methods flush only; callers own commits." |
| Endpoints import services, not crud/models/responders (for most endpoints) | **Done** (see exceptions below) |
| `BackgroundTasks` pattern in endpoints | 9 endpoint files use it (answers, articles, questions, submissions, comments, suggestions, feedbacks) |

### Layer sizes

| Layer | Modules | Total lines |
|-------|---------|-------------|
| `api/endpoints/` | 39 files | 3,704 |
| `services/` | 40 files | 6,817 |
| `responders/` | 15 files | 1,147 |
| `crud/` | 31 files | 2,298 |
| `infra/` | 6 files | 614 |

---

## Gaps (Step 4 — ongoing cleanup)

### 1. `CRUDBase` still alive

**File:** `chafan_core/app/crud/base.py` (105 lines)

28 crud modules still inherit from `CRUDBase`. The docstring acknowledges the transitional state: _"Prefer plain functions for new code; this base remains for migration."_ The proposal says `CRUDBase` should be deleted and modules demoted to plain functions.

**Action:** Replace each `CRUD*` class with plain functions, delete `base.py` when the last inheritor is gone.

---

### 2. `login.py` and `people.py` bypass the services layer

**Files:**
- `chafan_core/app/api/api_v1/endpoints/login.py` (545 lines)
- `chafan_core/app/api/api_v1/endpoints/people.py` (333 lines)

**Together: 31 direct `crud.*` calls** from endpoints — the largest remaining legacy surface. These two files are pre-service and haven't been migrated.

Examples from `people.py`:
- `crud.user.get_by_handle(db, handle=handle)` (line 133)
- `crud.user.get_by_uuid(ctx.get_db(), uuid=uuid)` (line 193, 259, 275, 296, 317, 332)
- `crud.topic.get_by_uuid(db, uuid=...)` (lines 44, 45, 65)

Examples from `login.py`:
- `crud.user.authenticate(...)` (line 123)
- `crud.user.get_by_email(db, email=email)` (lines 216, 294, 346, 372)
- `crud.user.create(db, obj_in=user_in)` (line 315)
- `crud.audit_log.create_with_user(...)` (lines 87, 223, 246, 280, 354)
- `crud.coin_payment.make_payment(...)` (line 187)
- `crud.coin_deposit.make_deposit(...)` (line 471)

**Action:** Extract business logic into `services/login.py` and `services/people.py`; endpoints shrink to parse → call service → return.

---

### 3. `responders/comment.py` imports `user_permission`

**File:** `chafan_core/app/responders/comment.py:31`

```python
from chafan_core.app.user_permission import user_in_site
```

The proposal states: **"Services call it; responders never do."** This is a layering violation. Permissions should be checked by the service before passing data to the responder.

**Action:** Move the `user_in_site` call up into the calling service; pass the result (or a pre-filtered list) to the responder.

---

### 4. `services/answers.py` queries `models` directly

**File:** `chafan_core/app/services/answers.py:47`

```python
db.query(models.Answer_Upvotes)
    .filter_by(answer_id=answer.id, voter_id=principal_id, cancelled=False)
    .first()
```

Services are allowed to import `crud`, but direct model queries bypass the crud layer. The proposal says crud owns all SQL statements.

**Action:** Add an `answer_upvotes` function to `crud/crud_answer.py` and call it from the service. Minor — low priority.

---

### 5. No import-linter enforcement

The proposal describes an optional ratchet: _"a small import-linter check (endpoints may not import crud/responders; responders may not import services; etc.) turns the architecture from convention into a CI guarantee."_

Not yet implemented.

---

## Architecture rule compliance

| Rule | Compliant? | Exceptions |
|------|-----------|------------|
| Endpoints may not import `crud/` | Mostly | `login.py`, `people.py` |
| Endpoints may not import `models` | Yes | — |
| Endpoints may not import `responders` | Yes | — |
| Services may not import endpoints | Yes | — |
| Responders may not import `user_permission` or services | Mostly | `comment.py` (user_permission) |
| Responders may not call `db.commit()` | Yes | — |
| CRUD may not call `db.commit()` | Yes | — |
| Services own `db.commit()` | Yes (29 locations across 15 files) | — |

---

## Timeline

| Step | Status |
|------|--------|
| Step 0 — Fix responder permission stubs | **Done** (user_permission.py exists, most responders fixed) |
| Step 1 — Materialize kill | **Done** |
| Step 2 — Dramatiq removal | **Done** |
| Step 3 — Cache reduction / CachedLayer breakup | **Done** |
| Step 4 — Services extraction + crud demotion | **In progress** (see gaps above) |
