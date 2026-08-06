# Chafan Core Backend Framework

[![Main test](https://github.com/chafan-dev/chafan-core/actions/workflows/main-test.yml/badge.svg?branch=main)](https://github.com/chafan-dev/chafan-core/actions/workflows/main-test.yml)

## Getting Started

### Requirements

- Linux or macOS
- [Nix](https://nixos.org/download) with flakes enabled — provides Python and all backend dependencies via `flake.nix`
- A running PostgreSQL server (any recent version) with a database you can write to
- A running Redis server

### Enter the dev shell

```bash
nix develop
```

This drops you into a shell with Python and every backend dependency available.

Run all subsequent commands **from the repository root**, inside this shell. Several tools depend on it: `alembic.ini` sets `script_location = alembic`, a relative path, so `alembic` outside the root fails with `No config file 'alembic.ini' found`. Set `PYTHONPATH` to the root as well, so that `chafan_core` is importable:

```bash
cd "$(git rev-parse --show-toplevel)"
export PYTHONPATH="$PWD"
```

### Configure environment

Settings are read from the environment; `.env` in the repository root is read too, and real environment variables win over it. See `chafan_core/app/config.py` for the full list of settings and their defaults.

Only three have no default and must be set: `DATABASE_URL`, `REDIS_URL`, and `SERVER_HOST`.

The quickest start is to copy `env.ci` — the configuration CI runs against, so it is known to work — and edit it:

```bash
cp env.ci .env
```

A minimal `.env` of your own:

```
SERVER_HOST=http://dev.cha.fan:4582
DATABASE_URL=postgresql://<user>@localhost:5432/chafan_dev
REDIS_URL=redis://127.0.0.1:6379
SERVER_NAME=dev.cha.fan
BACKEND_CORS_ORIGINS=["http://dev.cha.fan:8080"]
PROJECT_NAME=Chafan Dev
SECRET_KEY=change-me
FIRST_SUPERUSER=admin@cha.fan
FIRST_SUPERUSER_PASSWORD=change-me
USERS_OPEN_REGISTRATION=False
ENV=dev
```

### Point `dev.cha.fan` at your machine

The dev server binds the hostname `dev.cha.fan`, which resolves publicly to an address you cannot bind locally. Add it to `/etc/hosts` first, or `make dev-run` fails with `Cannot assign requested address`:

```
127.0.0.1 dev.cha.fan
```

### Initialize the database

```bash
alembic upgrade head
python scripts/initial_data.py
```

### Run the dev server

```bash
make dev-run
```

API docs: http://dev.cha.fan:4582/docs

## DB Schema Migrations

1. Edit models under `chafan_core/app/models` and update `chafan_core/app/models/__init__.py`.
2. Generate a revision:
   ```bash
   alembic revision --autogenerate -m "Add column last_name to User model"
   ```
   See the [Alembic autogenerate docs](https://alembic.sqlalchemy.org/en/latest/autogenerate.html). **Always inspect the generated file** before applying. In particular, give constraints an explicit name — an unnamed one leaves the downgrade with no name to drop.
3. Apply:
   ```bash
   alembic upgrade head
   ```
4. To roll back to a specific revision:
   ```bash
   alembic downgrade <revision-id>
   ```

The `Migrations` workflow tests migrations as a deliverable in their own right: exactly one head, a build from scratch, no drift between models and migrations (`alembic check`), and a downgrade/upgrade round-trip of the migrations the pull request adds, run against a populated database. See `.github/workflows/migrations.yml`.

## Tests

`scripts/reset_app_state.sh` gives you a clean slate. **It drops and recreates the `chafan_dev` database and flushes Redis** — everything in your dev database is lost. It connects as the `postgres` superuser on `localhost:5432`.

```bash
bash scripts/reset_app_state.sh
pytest
```

A single file:

```bash
pytest -vv chafan_core/tests/app/email/test_email.py
```

The tests share one database and do not isolate themselves from each other, so a reset between full runs is the reliable way to run them. CI splits the suite across five jobs (search/feed/permission, two CRUD halves, API, email); see `.github/workflows/main-test.yml`.

### End-to-end smoke suite

`smoke/` is a separate suite that drives a live server over HTTP, in bootstrap mode: fresh database, migrate, seed fixtures, start uvicorn, run the suite.

```bash
bash scripts/e2e/run_e2e_smoke.sh
```

It expects the repository root as the working directory, Postgres and Redis up, the environment sourced, and the nix dev shell — the same preconditions CI sets up in `.github/workflows/e2e-smoke.yml`. `smoke/dataset` also defines the seeded dataset that the migrations workflow runs against.

## Checks before a pull request

```bash
make format   # isort, autoflake, black
make check    # architecture ratchets, mypy, black/isort/flake8, event-table consistency
```

`make check` runs `scripts/static_analysis/lint.sh` — the same script the `Static Analysis` workflow runs — plus `scripts/check.py`, which asserts that every event verb has a row in both `EVENT_TEMPLATES` and the distribution policy table. The two architecture ratchets (`check_layer_imports.py`, `check_service_commits.py`) must pass; the formatting and typing checks are advisory.

## How to add a new event type

- Core backend
  - Add event definition: `chafan_core/app/schemas/event.py`
  - Add a policy row for the verb: `chafan_core/app/services/activity_policy.py` (`POLICY`) — this is what decides whether the event is published as an `Activity`, which `Audience` receives it in the feed, and which audiences are notified. `chafan_core/app/services/events.py` resolves those audiences and is the single place an event reaches its sinks.
  - If the event goes to notifications:
    - `chafan_core/app/responders/event.py`: `materialize_event` (if a new field type)
    - `chafan_core/app/common.py`: `EVENT_TEMPLATES`
- PWA ([chafan-dev/chafan-pwa](https://github.com/chafan-dev/chafan-pwa))
  - Add event definition: `src/interfaces/index.ts`
  - If the event goes to the activity feed: update event card in `src/views/main/Home.vue`
  - Update event field rendering: `src/components/Event.vue` (if a new field type)
  - Update event translation rendering: `src/main.ts`

## Documentation

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — the prod-first principle: when prod code and the test suite disagree, prod is the spec.
- [`docs/glossary.md`](docs/glossary.md) — event, activity, feed, notification, and the other vocabulary of this codebase.
- [`docs/proposals/`](docs/proposals) — design documents, each with a status header:
  - [Target Architecture](docs/proposals/2026-07-15-target-architecture.md) — the layering the codebase is moving to, and the import rule CI enforces.
  - [Event distribution](docs/proposals/2026-08-03-event-distribution.md) — one seam for Activity, Feed and Notification.
  - [Activity as the event log, Feed as a receiver index](docs/proposals/2026-08-04-activity-feed-reassignment.md)

## Copyright

For all files within this repo, see `LICENSE` for the default copyright, unless a file declares otherwise.
