# Chafan Core Backend Framework

Under active construction!! 🚧

## Getting Started

### Requirements

- Linux or Unix environment
- Terminal
- VS Code
- Postgre DB for development, with a new user
  - If you are using macOS, try https://postgresapp.com
- Redis for developement
  - If you are using macOS, see https://redis.io/docs/getting-started/installation/install-redis-on-mac-os/

### Set up editor

- Install Poetry package manager https://python-poetry.org
- `poetry install` to create virtual env and install all Python dependencies
- `poetry shell` to enter the virtual env. You need to run this everytime in this repo before running other commands that depends on Python code.
- `make link-venv` to create a symbolic to virtual env such that VSCode is happy (if necessary, Run "Reload window" and make sure that the Python environment is `.venv`).
- Use VSCode with [Python extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python) (Pylance is recommended).

## Develop server locally

Example `.env` for basic development (update `DATABASE_URL` and `REDIS_URL` if necessary):

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
```

Run following commands to create database and initialize `chafan_dev` table.

```bash
# Run migrations
alembic upgrade head

# Create initial data in DB
python scripts/initial_data.py
```
