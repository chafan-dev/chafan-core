set -ex
base=$(git rev-parse --show-toplevel)
cd "$base"
source $base/../launch_env

redis-server --port $CHAFAN_REDIS_PORT
