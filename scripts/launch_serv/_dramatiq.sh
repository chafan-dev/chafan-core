set -ex

base=$(git rev-parse --show-toplevel)
cd "$base"
source $base/../launch_env

dramatiq --threads 2 chafan_core.app.task


