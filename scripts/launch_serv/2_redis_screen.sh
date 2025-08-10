base=$(git rev-parse --show-toplevel)
cd "$base"

#screen -S redis bash -c "bash $base/scripts/launch_serv/_redis.sh"
screen -S redis bash -c \
    "nix develop --command $base/scripts/launch_serv/_redis.sh"


