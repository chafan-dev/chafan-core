# Chafan Core Backend Framework

[![Main test](https://github.com/chafan-dev/chafan-core/actions/workflows/main-test.yml/badge.svg?branch=main)](https://github.com/chafan-dev/chafan-core/actions/workflows/main-test.yml)

Under active construction!! 🚧

## Getting Started

### Requirements

- Linux or Unix environment
- Terminal
- VS Code
- Postgre DB for development, with a new user
  - macOS: https://postgresapp.com
  - Remember to add the command line utils to `$PATH`.
  - Run `create database chafan_dev;`.
- Redis for developement
  - macOS: https://redis.io/docs/getting-started/installation/install-redis-on-mac-os/
- RabbitMQ for development:
  - macOS: `brew install rabbitmq` (see more in "RabbitMQ dev setup in macOS")

### Set up editor

- Install Poetry package manager https://python-poetry.org
- `poetry install` to create virtual env and install all Python dependencies
- `poetry shell` to enter the virtual env. You need to run this everytime in this repo before running other commands that depends on Python code.
- `make link-venv` to create a symbolic to virtual env such that VSCode is happy (if necessary, Run "Reload window" and make sure that the Python environment is `.venv`).
- Use VSCode with [Python extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python) (Pylance is recommended).

## Develop server locally

Example `.env` for basic development (update `DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL` if necessary):

```
SERVER_NAME=dev.cha.fan
SERVER_HOST=http://dev.cha.fan:4582
BACKEND_CORS_ORIGINS=["http://dev.cha.fan:8080"]
PROJECT_NAME=Chafan Dev
SECRET_KEY=chafandev
FIRST_SUPERUSER=admin@cha.fan
FIRST_SUPERUSER_PASSWORD=superuser
USERS_OPEN_REGISTRATION=False
DATABASE_URL=postgresql://chafan@localhost:5432/chafan_dev
ENV=dev
REDIS_URL=redis://127.0.0.1:6379
RABBITMQ_URL=amqp://guest:guest@localhost:5672/%2f
```

Run following commands to create database and initialize `chafan_dev` table.

```bash
# Run migrations
alembic upgrade head

# Create initial data in DB
python scripts/initial_data.py
```

After initialization, run dev server:

```
make dev-run
```

Open http://dev.cha.fan:4582/docs for API docs.

## DB Schema Migrations

### Step 1: Set up python dependencies and Shell envs

```
nix develop
source ../launch_env
echo $DATABASE_URL
```

### Step 2: Run PostgreSQL
```
pg_ctl start -l logfile   -D   $CHAFAN_PG_DB_CLUSTER -o "--unix_socket_directories='$CHAFAN_PG_DB_BASE'  -p $CHAFAN_PG_PORT"
```

### Step 3: Edit models

- Modify `app/models`
- Also modify `app/models/__init__.py`

### Step 4: Generate version file


```bash
alembic revision --autogenerate -m "Add column last_name to User model"
```

See [doc](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) and [StackOverflow](https://stackoverflow.com/questions/11180013/auto-generating-migrations-using-alembic/11193390#11193390)


SHALL manually check the generated version file, eg `4794c0c3c743_add_view_count_tables.py`

### Step 5: Apply DB change

```
alembic upgrade head
```

Check PostgreSQL DB and `TABLE alembic_version`.

### Step 6: If we need to downgrade

```
alembic downgrade 6162e247214e
```

## Test

Reset persistent state before testing:

```
bash scripts/reset_app_state.sh
```

Test a single file:

```
pytest -vv chafan_core/tests/app/email/test_email.py

```

Test all:

```
pytest
```


## Staging

`stag` branch is automatically pushed to the following endpoint for testing:

```
https://chafan-test.dokku.cha.fan/
```

# How to add a new event type

- Core backend code changes
  - Add event definition: `chafan_core/app/schemas/event.py`
  - If the event goes to activity feed
    - Feed distribution: `chafan_core/app/feed.py:get_activity_receivers`
  - If the event goes to notifications
    - `chafan_core/app/materialize.py`: `materialize_event` and `_KEYS` (if there is a new type of field)
    - `chafan_core/app/common.py`: `EVENT_TEMPLATES`
- PWA code changes
  - Add event definition: `src/interfaces/index.ts`
  - If the event goes to activity feed
    - Update event card: `src/views/main/Home.vue`
  - Update event field rendering: `src/components/Event.vue` (if there is a new type of field)
  - Update event translation rendering: `src/main.ts`

## Dependency

Run `poetry update` to update all dependencies.

## Copyright

For all files within this repo, see `LICENSE` for default copyright unless otherwise declared in file:
