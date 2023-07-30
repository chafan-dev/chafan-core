web: alembic upgrade head; uvicorn chafan_core.app.main:app --port=$PORT --host=0.0.0.0 --log-level=$LOG_LEVEL
worker: bash scripts/dramatiq_worker.sh
