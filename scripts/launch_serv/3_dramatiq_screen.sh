base=$(git rev-parse --show-toplevel)
cd "$base"

screen -S dramatiq bash -c \
    "nix develop --command $base/scripts/launch_serv/_dramatiq.sh"
