# Deferred: Unit of Work (Commit at Request Boundary)

**Source:** v1 `proposals/12-async-migration.md` Part B.

**Status:** Deferred, stands on its own merits, revisit after v2.

---

## Summary of the proposal

Move `db.commit()` from inside every CRUD method to the request boundary. Today:

```python
def create(self, db, *, obj_in):
    db.add(db_obj)
    db.commit()  # Can't group with other operations
```

Problem: multi-step operations can't be atomic. Partial failures leave inconsistent state.

Target:

```python
def create(self, db, *, obj_in):
    db.add(db_obj)
    db.flush()  # Get IDs without committing
    return db_obj

# deps.py
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

Dramatiq actors and scheduled jobs own their own `commit()` explicitly (they run outside the request lifecycle).

## Why deferred

- Highest-risk change in the whole plan. Every CRUD method and every caller that assumes immediate commit must be audited.
- v2 already addresses the most visible symptom (coin/karma scattered mutations → centralized in `rep_manager` via `08-rep-manager-centralization.md`) even though rep_manager itself still depends on the caller owning the commit.
- Per memory: coins are anti-spam, not currency. Atomicity fixes are cleanup, not urgent.
- Depends on a robust test suite to catch regressions. v2 deliberately avoids heavy test infrastructure investment until prod is stable.

## Independent of async

This stands on its own. It's not coupled to the async migration even though v1 bundled them. It can ship whenever the time and risk budget allow — after v2 is done and prod is calm.

## Trigger for revisiting

- A concrete atomicity bug causes user-visible inconsistency (beyond the coin edge cases already known to be tolerable).
- A new feature requires multi-step transactions that can't be made atomic with the current design.

## Prerequisites (before picking this up)

- v2 is complete and stable in prod.
- There's a test-isolation story that can catch regressions (either the good-state rule has been sufficient, or dedicated transaction-per-test infra has been added).
- Time for a multi-week audit pass across every CRUD method.
