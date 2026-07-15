#!/usr/bin/env bash
# End-to-end smoke run in *bootstrap* mode.
#
#   fresh DB -> migrate -> seed fixtures -> live uvicorn + dramatiq -> smoke suite
#
# Preconditions (the caller sets these up):
#   - cwd is the repo root,
#   - a Postgres + Redis reachable per DATABASE_URL / REDIS_URL are up,
#   - the app env is already sourced (e.g. `source env.ci`),
#   - we are inside the nix devShell so uvicorn/dramatiq/alembic are on PATH.
#
# In CI this runs inside `nix develop --command`. Locally you can run it the
# same way from a checkout with Postgres/Redis available.
#
# Exit 0 = smoke suite passed. Non-zero = something regressed; server and
# worker logs are dumped to aid diagnosis.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"

HOST_ADDR=127.0.0.1
PORT=8000
READY_URL="http://${HOST_ADDR}:${PORT}/api/v1/category-topics/"
READY_TIMEOUT=60

LOG_DIR="$(mktemp -d)"
SERVER_LOG="$LOG_DIR/uvicorn.log"
WORKER_LOG="$LOG_DIR/dramatiq.log"

server_pid=""
worker_pid=""

dump_logs() {
    echo "----- dramatiq worker log -----"
    tail -n 100 "$WORKER_LOG" 2>/dev/null || true
    echo "----- uvicorn server log -----"
    tail -n 100 "$SERVER_LOG" 2>/dev/null || true
}

cleanup() {
    local code=$?
    [ -n "$server_pid" ] && kill "$server_pid" 2>/dev/null || true
    [ -n "$worker_pid" ] && kill "$worker_pid" 2>/dev/null || true
    if [ "$code" -ne 0 ]; then
        echo "==> e2e smoke FAILED (exit $code); dumping logs"
        dump_logs
    fi
    exit "$code"
}
trap cleanup EXIT

echo "==> Migrate database"
alembic upgrade head

echo "==> Create initial data (superuser = user id 1)"
python scripts/initial_data.py

echo "==> Seed bootstrap fixtures (writes smoke/config.json)"
python smoke/seed.py

echo "==> Launch dramatiq worker"
dramatiq --threads 2 chafan_core.app.task >"$WORKER_LOG" 2>&1 &
worker_pid=$!

echo "==> Launch uvicorn server"
uvicorn chafan_core.app.main:app --host "$HOST_ADDR" --port "$PORT" \
    >"$SERVER_LOG" 2>&1 &
server_pid=$!

echo "==> Wait for server readiness"
if ! python scripts/e2e/wait_ready.py "$READY_URL" "$READY_TIMEOUT"; then
    echo "server never became ready" >&2
    exit 1
fi

# A dead worker would make s10/s11 fan-out polling time out and read as a
# real regression, so fail fast and clearly if it already crashed.
if ! kill -0 "$worker_pid" 2>/dev/null; then
    echo "dramatiq worker exited before smoke run" >&2
    exit 1
fi

echo "==> Run smoke suite (bootstrap mode)"
cd smoke
python run_all.py
