# Chafan Core Backend Framework

[![Main test](https://github.com/chafan-dev/chafan-core/actions/workflows/main-test.yml/badge.svg?branch=main)](https://github.com/chafan-dev/chafan-core/actions/workflows/main-test.yml)

## Getting Started

### Requirements

- Linux or macOS
- [Nix](https://nixos.org/download) with flakes enabled

That is the whole list. `flake.nix` provides Python and every backend dependency, PostgreSQL 14, Redis, and the formatters and linters, so the dev shell is self-contained. The one thing it cannot ship is a container runtime — Podman or Docker — and that is needed only for the optional object store in [Image uploads](#image-uploads-optional).

### Enter the dev shell

```bash
nix develop
```

Besides Python, this puts `alembic`, `uvicorn`, `pytest`, `black`, `isort`, `autoflake`, `mypy`, `flake8`, `psql`, `postgres`, `redis-server` and `redis-cli` on `PATH`.

Run all subsequent commands **from the repository root**, inside this shell. Several tools depend on it: `alembic.ini` sets `script_location = alembic`, a relative path, so `alembic` outside the root fails with `No config file 'alembic.ini' found`. Set `PYTHONPATH` to the root as well, so that `chafan_core` and `smoke` are importable:

```bash
cd "$(git rev-parse --show-toplevel)"
export PYTHONPATH="$PWD"
```

### Start PostgreSQL and Redis

The shell ships both servers but starts neither, and nothing below works until they are up. Any instance reachable at your `DATABASE_URL` and `REDIS_URL` will do; the shortest path is to run them out of the shell itself:

```bash
initdb -U postgres -D "$PWD/.pgdata"                       # once
pg_ctl -D "$PWD/.pgdata" -l "$PWD/.pgdata/logfile" start
redis-server --daemonize yes
```

`-U postgres` matters: it names the cluster superuser `postgres`, which is the user `env.ci` connects as. A cluster created this way trusts local connections, so the password in `DATABASE_URL` is ignored.

Containers work equally well and are what CI runs:

```bash
podman run -d --name chafan-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:14
podman run -d --name chafan-redis -p 6379:6379 redis
```

A container Postgres does check the password, so keep `PGPASSWORD=postgres` in your environment — that is what lets the `psql` commands below run without prompting.

### Configure environment

Settings are read from **environment variables, and nothing else** — there is no `.env` support, deliberately. Deployments keep their configuration in a file outside the checkout, because it holds secrets that must not sit in a tracked directory; a `.env` inside the repository would be a second place for those to end up. See `chafan_core/app/config.py` for the full list of settings and their defaults.

Only three have no default and must be set: `DATABASE_URL`, `REDIS_URL`, and `SERVER_HOST`.

The quickest start is `env.ci` — the configuration CI runs against, so it is known to work. Copy it, edit it, and **export it while sourcing**:

```bash
cp env.ci env.dev
$EDITOR env.dev
set -a; source env.dev; set +a
```

`set -a` is the part that matters. A plain `source env.dev` sets shell variables without exporting them, so `alembic`, `pytest` and `uvicorn` — separate processes — see nothing, and fail with `Field required` and `input_value={}`. Every environment step in `.github/workflows/` is written this way for the same reason.

A minimal configuration of your own:

```
SERVER_HOST=http://localhost:8080
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/chafan_dev
REDIS_URL=redis://127.0.0.1:6379
PGPASSWORD=postgres
CHAFAN_BACKEND_CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
PROJECT_NAME=Chafan Dev
SECRET_KEY=change-me
FIRST_SUPERUSER=admin@cha.fan
FIRST_SUPERUSER_PASSWORD=change-me
USERS_OPEN_REGISTRATION=False
ENV=dev
```

Two of those are easy to get wrong:

- **`SERVER_HOST` is the frontend, not this server.** It is the base for links the backend builds into emails, RSS items and event templates — `{SERVER_HOST}/reset-password?token=...`, `{SERVER_HOST}/questions/...`. Those are PWA routes, so point it at wherever the PWA is served, not at the API port, or every emailed link lands on the API server.
- **`CHAFAN_BACKEND_CORS_ORIGINS` is a comma-separated string**, not a JSON list, and the name carries the `CHAFAN_` prefix. Its default is `https://127.0.0.1:8080`, so a PWA served from any other origin is blocked until you list that origin here. Both values above assume the PWA on `localhost:8080`; under a tunnel they become the public hostname instead (see [Reaching it from a browser](#reaching-it-from-a-browser)). `DEBUG_BYPASS_BACKEND_CORS=magic` allows every origin instead — a dev-only shortcut that the app refuses to start with when `ENV=prod`.

### Create and initialize the database

The database itself is not created for you — `alembic` expects it to exist. Derive it from the `DATABASE_URL` you just exported, rather than retyping the connection details: `${DATABASE_URL%/*}` is the same server with the database name stripped off, so pointing it at the always-present `postgres` database gives you a connection from which to create your own.

```bash
psql "${DATABASE_URL%/*}/postgres" -c "create database ${DATABASE_URL##*/};"
alembic upgrade head
python scripts/initial_data.py
```

Written this way the step follows whatever `DATABASE_URL` says — the local `chafan_dev` above, or the host, port, user and database name of a deployment whose environment file lives outside the checkout. `alembic` and `initial_data.py` already read the same variable.

`initial_data.py` inserts exactly one row: the superuser from `FIRST_SUPERUSER`. For a database you can actually click around in, build the shared development dataset as well — eight users with karma and coins, a site with three columns, questions, answers, articles, and the follow/upvote/comment graph between them:

```bash
python -m smoke.dataset build --deep
```

`--deep` adds an extra answer and the Activity/Feed/Notification rows behind it, so the feed and notification screens have something to show. This is the same dataset the e2e smoke suite seeds and the `Migrations` workflow migrates across (`smoke/dataset/`), which is why it keeps up with the schema. It is idempotent: re-running it against a seeded database is a no-op. Sign in as `smoke-a@cha.fan` / `smoke-pw-a1` (superuser) or `smoke-b@cha.fan` / `smoke-pw-b1`; the rest of the accounts are in `smoke/dataset/models/user_factory.py`.

### Run the dev server

```bash
uvicorn chafan_core.app.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs: http://127.0.0.1:8000/docs — served only when `ENV=dev`. Loopback and port 8000 are what the rest of the repo assumes: `scripts/e2e/run_e2e_smoke.sh` and `scripts/launch_serv/_fastapi.sh` both use them.

### Reaching it from a browser

Two setups are in use, and neither wants an `/etc/hosts` entry — the server always binds loopback.

**Local only.** Run the PWA's dev server on `localhost:8080`, point it at `http://127.0.0.1:8000`, and list its origin in `CHAFAN_BACKEND_CORS_ORIGINS` as the example config above does. Nothing leaves the machine.

**Published over a Cloudflare tunnel.** For testing from a phone, another machine, or by someone else, `cloudflared` fronts the same loopback server: the backend is published as `api_dev.cha.fan` and the PWA as `dev.cha.fan`, so the public hostnames resolve to Cloudflare rather than to you.

```bash
cloudflared tunnel --no-autoupdate run --token "$CF_TUN_TOKEN"
```

`cloudflared` comes with the dev shell. `scripts/launch_serv/5_cloudflared_screen.sh` runs exactly that line, reading `CF_TUN_TOKEN` from a `launch_env` file kept **outside** the checkout — same reason the app config lives outside it. Which hostname maps to which local port is configured in the Cloudflare dashboard, not in this repo.

In that setup the two front-end-facing settings follow the public names:

```
SERVER_HOST=https://dev.cha.fan
CHAFAN_BACKEND_CORS_ORIGINS=https://dev.cha.fan
```

`scripts/launch_serv/` holds the rest of that workflow — Postgres, Redis, uvicorn and the tunnel, each in its own `screen` session.

### Image uploads (optional)

Uploads go to an S3-compatible object store (Storm Buckets in production). With the `UPLOADS_S3_*` settings unset the endpoint rejects every upload with `503 Image uploads are not configured on this server.` and nothing else is affected, so skip this section unless you are working on uploads.

MinIO gives you a local one, the same way `.github/workflows/e2e-smoke.yml` does:

```bash
podman run -d --name chafan-minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

Add to your environment, then create the bucket:

```
UPLOADS_S3_ENDPOINT_URL=http://localhost:9000
UPLOADS_S3_ACCESS_KEY_ID=minioadmin
UPLOADS_S3_SECRET_ACCESS_KEY=minioadmin
UPLOADS_S3_BUCKET=chafan-dev
UPLOADS_S3_REGION=us-east-1
UPLOADS_PUBLIC_URL_BASE=http://localhost:9000/chafan-dev
```

```bash
python scripts/e2e/ensure_upload_bucket.py
```

`UPLOADS_PUBLIC_URL_BASE` is only ever used to build the stored URL (`<base>/<sha>.<ext>`); the backend never reads back through it. The value above resolves in a browser only if the bucket allows anonymous reads — CI does not bother, and uses `https://uploads.cha.fan`, because the smoke suite asserts the shape of the URL rather than fetching it.

Who may upload and what it costs are product rules rather than settings: the karma gate and coin price live in `chafan_core/app/rules.py`, the size cap in `chafan_core/app/common.py`. To find uploads that no body references any more:

```bash
python scripts/upload_report.py              # list orphans
python scripts/upload_report.py --sha=<sha>  # usages of a single sha
```

Nothing is deleted by that script — the bucket is treated as losable and the `upload` table is the recovery manifest.

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

Start from a clean slate. **The first three commands flush Redis and drop and recreate the `chafan_dev` database** — everything in your dev database is lost:

```bash
redis-cli flushall
psql -h localhost -p 5432 -U postgres -c 'drop database chafan_dev WITH (FORCE);'
psql -h localhost -p 5432 -U postgres -c 'create database chafan_dev;'
alembic upgrade head
python scripts/initial_data.py
pytest
```

Unlike [creating the database](#create-and-initialize-the-database) above, these spell the connection out instead of deriving it from `DATABASE_URL`, and that asymmetry is deliberate: a `drop database` that follows the environment destroys whatever the environment happens to point at, which for a deployment is the live database. Pinned to `localhost:5432` and `chafan_dev`, a misfire under the wrong environment reaches nothing instead.

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
bash scripts/format.sh                 # isort, autoflake, black
bash scripts/static_analysis/lint.sh   # architecture ratchets, mypy, black/isort/flake8
python scripts/check.py                # event-table consistency
```

`lint.sh` is the same script the `Static Analysis` workflow runs. Its three architecture ratchets (`check_layer_imports.py`, `check_service_commits.py`, `check_rules_applied.py`) must pass; the formatting and typing checks are advisory. `scripts/check.py` asserts that every event verb has a row in both `EVENT_TEMPLATES` and the distribution policy table.

Two maintenance scripts are worth knowing about:

```bash
python scripts/refresh_karmas.py           # report karma that disagrees with rules.py
python scripts/refresh_karmas.py --apply   # write the recomputed values
bash scripts/compile_email_templates.sh    # rebuild the email HTML from the .mjml sources
```

`compile_email_templates.sh` is the one command here that needs something the dev shell does not carry: `mjml`, from npm (`npm install -g mjml`) — nixpkgs 25.05 dropped `nodePackages.mjml`. It is only needed when an email template changes; the compiled HTML under `email-templates/build` is committed and is what the app reads at runtime. MJML is being kept as the authoring format for now, so that npm dependency is a decision rather than an oversight; the reasoning, and what to do instead if it ever stops paying for itself, is in the script's header.

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
