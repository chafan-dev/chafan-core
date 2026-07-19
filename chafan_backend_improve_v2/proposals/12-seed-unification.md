# 12: Seed Data Unification — Kill the UUID Env Vars

**Phase:** 1 — Code correctness | **Effort:** 1 day | **Risk:** Low

**Supersedes:** `06-dev-prod-unification.md` sub-item A7.

---

## Problem

Several components assume the DB has been pre-seeded with specific rows, and they locate those rows by passing UUIDs/IDs in environment variables. This is ugly for multiple reasons:

- **Config is lying.** An env var called `WELCOME_TEST_FORM_UUID` implies a configurable identifier, but in practice everyone must use the exact UUID that matches the seeded DB. It's a hardcoded handshake dressed up as config.
- **Dev-prod skew.** Dev bypasses the lookup via `is_dev()` (directly relevant to the `06-dev-prod-unification.md` push). Prod relies on someone having set the env var correctly to an externally-defined UUID. Neither environment looks the other in the eye.
- **Broken-out-of-box dev.** A dev who follows the setup instructions gets a DB without the expected rows, and the app either silently bypasses (dev) or errors out (prod). There's no single "seed my empty DB" path.
- **Not just UUIDs.** The pattern extends to the visitor user (looked up by integer ID in `VISITOR_USER_ID`) and the admin credentials (`FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD`).

## What exists today

Seeding code: `chafan_core/db/init_db.py` — creates only the superuser from `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD`. Everything else is "good luck, hope the DB has what you need."

UUID/ID env params and their usage:

| Env param | Default | Used by | What it identifies |
|-----------|---------|---------|--------------------|
| `WELCOME_TEST_FORM_UUID` | `"4CGv4iReMxuWjs3T2PEY"` | `login.py:456` (form-reward validation) | A specific `Form` row |
| `VISITOR_USER_ID` | `None` | `crud_user.py:128-130` (`try_get_visitor_user`), `task.py:571, 590` (Dramatiq skip) | The "visitor" user row |
| `FIRST_SUPERUSER` | `None` | `init_db.py:20-25`, `tests/utils/utils.py:42`, test files | Admin email (seed input, not lookup) |
| `FIRST_SUPERUSER_PASSWORD` | `None` | Same as above | Admin password (seed input, not lookup) |

Note the distinction: `FIRST_SUPERUSER*` are **seed inputs** (we set the admin credentials at deploy time — reasonable), while the other two are **lookups against pre-seeded rows** (we make the app look up a hardcoded row by UUID/ID — ugly).

## Decision

(a) vs. (b) from the Q8 discussion — **chose (b): unify initial seeding and remove the UUID lookup env params.** Rationale: the "make it work with empty DB" path (a) would push per-callsite nullability into otherwise clean code and doesn't help — the app genuinely depends on certain rows existing (a visitor user, a welcome form). Seed them honestly.

## Fix

### 1. Extend `init_db.py` with `seed_required_data()`

```python
# chafan_core/db/init_db.py
def seed_required_data(db: Session) -> None:
    _ensure_superuser(db)         # existing behavior, refactored out
    _ensure_visitor_user(db)      # NEW — lookup by handle="visitor"
    _ensure_welcome_form(db)      # NEW — lookup by a known attribute, not UUID
```

Invariant: **idempotent.** Safe to call on first boot, safe to call on every boot. If the row already exists, do nothing.

### 2. Replace UUID/ID lookups with handle/attribute lookups

- `VISITOR_USER_ID` → replace with a visitor user looked up by `handle="visitor"` in `crud.user.try_get_visitor_user`. Delete the env var.
- `WELCOME_TEST_FORM_UUID` → the form doesn't need a fixed UUID. Either:
  - **Option A (preferred):** look the form up by a stable `code` / `slug` attribute that `seed_required_data` sets (e.g. `form.code == "welcome_test"`).
  - **Option B:** generate a random UUID at seed time, store a well-known `code`, and look up by `code`.

  Either way, `login.py:456` stops comparing against `settings.WELCOME_TEST_FORM_UUID` and instead compares against a looked-up-by-code form's UUID. Delete the env var.

If the `Form` model has no `code`/`slug` field, add one via a lightweight migration or repurpose an existing field (`title`?). Check first — may already have something usable.

### 3. Wire `seed_required_data` into app startup (dev/stag/prod alike)

Per the "no seed script, no make target" principle from `06-dev-prod-unification.md`: call `seed_required_data(db)` from the FastAPI startup hook in `main.py`, right after DB session is available. Idempotent, so every boot is fine.

Alternative: keep it out of web startup, call it from a one-time `python -m chafan_core.db.init_db` CLI. Pick whichever matches the existing deploy flow. If unsure, go with startup hook — it's one less thing for a deployer to remember.

### 4. Delete env params

- Remove `WELCOME_TEST_FORM_UUID` from `config.py`.
- Remove `VISITOR_USER_ID` from `config.py`.
- Remove any references to them in `.env.example` / documentation.

Keep `FIRST_SUPERUSER` and `FIRST_SUPERUSER_PASSWORD` as env params — they are seed inputs (credentials we want configurable at deploy time), not lookup keys. Document them in `.env.example` as "initial admin credentials on first boot."

### 5. Delete the `is_dev()` bypass at `login.py:456`

Once the lookup is against a seeded row that's guaranteed present in dev and prod, the `is_dev()` bypass disappears. This is the A7 removal that `06` punts to this proposal.

## Edge cases to handle

- **Existing prod DB.** If a prod DB already has rows keyed by the old `WELCOME_TEST_FORM_UUID`, the seed function must detect that row and adopt it (set its `code` / don't create a duplicate). Migration strategy: `seed_required_data` checks for the form by `code`; if not found, falls back to looking up by the old UUID value (if set) and adopts it. After one boot, the env var is unnecessary; after deletion, only the code-based lookup remains.
- **Test DB.** Tests that previously set `WELCOME_TEST_FORM_UUID` and created the form manually should call `seed_required_data(db)` in a conftest fixture. Tests that don't touch the form stop caring.
- **Ordering with migrations.** `seed_required_data` runs *after* schema migrations. Do not confuse seed with schema.

## Acceptance

- `config.py` has no `WELCOME_TEST_FORM_UUID` or `VISITOR_USER_ID`.
- `init_db.seed_required_data(db)` is called once per boot (or via CLI) and is idempotent.
- `login.py:456` has no `is_dev()` bypass and compares against a form located via `seed_required_data`.
- `crud.user.try_get_visitor_user` looks up by `handle="visitor"`, not an env var ID.
- Dev and prod both boot cleanly from an empty DB (schema migrated, nothing else) — `seed_required_data` fills in what's needed.
- Existing prod data is preserved: no double-created rows on first-boot-after-upgrade.
- Test suite either passes or is adjusted to call `seed_required_data` in shared fixtures.

## Dependency notes

- Does **not** block `06-dev-prod-unification.md`. `06` can ship its other A-items first; A7 waits for this proposal. Both could land in the same PR if convenient.
- Does not block or get blocked by `08-rep-manager-centralization.md`.
- Does not block or get blocked by `15-image-upload-r2.md`.

## Out of scope

- Seeding example content (sites, questions) for a demo environment. If needed, that's a separate `seed_demo_data(db)` function — not part of this proposal.
- Rewriting `FIRST_SUPERUSER` handling. It's a seed input, not a lookup; leave it alone.
- A "factory reset" / "wipe and reseed" CLI. Nice to have, separate work.
