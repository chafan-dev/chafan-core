# Chafan Core Backend Framework

[![Main test](https://github.com/chafan-dev/chafan-core/actions/workflows/main-test.yml/badge.svg?branch=main)](https://github.com/chafan-dev/chafan-core/actions/workflows/main-test.yml)

Under active construction!! 🚧

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

This drops you into a shell with Python and every backend dependency available. Run all subsequent commands from inside this shell.

### Configure environment

Create a `.env` (or export the variables in your shell) with at minimum:

```
SERVER_NAME=dev.cha.fan
SERVER_HOST=http://dev.cha.fan:4582
BACKEND_CORS_ORIGINS=["http://dev.cha.fan:8080"]
PROJECT_NAME=Chafan Dev
SECRET_KEY=change-me
FIRST_SUPERUSER=admin@cha.fan
FIRST_SUPERUSER_PASSWORD=change-me
USERS_OPEN_REGISTRATION=False
DATABASE_URL=postgresql://<user>@localhost:5432/chafan_dev
REDIS_URL=redis://127.0.0.1:6379
ENV=dev
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
   See the [Alembic autogenerate docs](https://alembic.sqlalchemy.org/en/latest/autogenerate.html). **Always inspect the generated file** before applying.
3. Apply:
   ```bash
   alembic upgrade head
   ```
4. To roll back to a specific revision:
   ```bash
   alembic downgrade <revision-id>
   ```

## Tests

Reset persistent state, then run:

```bash
bash scripts/reset_app_state.sh
pytest
```

A single file:

```bash
pytest -vv chafan_core/tests/app/email/test_email.py
```

## How to add a new event type
- Core backend
  - Add event definition: `chafan_core/app/schemas/event.py`
  - If the event goes to the activity feed: update `chafan_core/app/feed.py:get_activity_receivers`
  - If the event goes to notifications:
    - `chafan_core/app/materialize.py`: `materialize_event` and `_KEYS` (if a new field type)
    - `chafan_core/app/common.py`: `EVENT_TEMPLATES`
- PWA
  - Add event definition: `src/interfaces/index.ts`
  - If the event goes to the activity feed: update event card in `src/views/main/Home.vue`
  - Update event field rendering: `src/components/Event.vue` (if a new field type)
  - Update event translation rendering: `src/main.ts`

## Copyright

For all files within this repo, see `LICENSE` for default copyright unless otherwise declared in file:
