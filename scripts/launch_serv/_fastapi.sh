set -ex

base=$(git rev-parse --show-toplevel)
cd "$base"
source $base/../launch_env

uvicorn chafan_core.app.main:app --host 127.0.0.1 --port 8000 | tee $FASTAPI_LOG_PATH

