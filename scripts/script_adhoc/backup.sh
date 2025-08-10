base=$(git rev-parse --show-toplevel)
cd "$base"

nix develop --command bash -c "bash $base/scripts/script_adhoc/_backup_db.sh"
