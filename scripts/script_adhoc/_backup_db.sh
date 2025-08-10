set -xe

base=$(git rev-parse --show-toplevel)
cd "$base"

source $base/../launch_env
backup_file_name=$HOME/backup_data_$(date +"%Y-%m-%d")

pg_ctl    -D   $CHAFAN_PG_DB_CLUSTER  status

psql -h 127.0.0.1 -p  $CHAFAN_PG_PORT --list



pg_dump -U $CHAFAN_UNIX_USER_NAME \
    -h 127.0.0.1 \
    -p $CHAFAN_PG_PORT \
    --compress=zstd:9 \
    --format=custom \
    --file="$backup_file_name" \
    $CHAFAN_SQL_DATABASE_NAME


ls -lh "$backup_file_name"
