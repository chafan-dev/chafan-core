base=$(git rev-parse --show-toplevel)
cd "$base"
screen -S fastapi bash -c \
    "nix develop --command $base/scripts/launch_serv/_fastapi.sh"


