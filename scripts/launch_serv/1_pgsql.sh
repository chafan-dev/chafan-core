base=$(git rev-parse --show-toplevel)
cd "$base"
nix develop --command $base/scripts/launch_serv/_pgsql.sh


