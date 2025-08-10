set -ex

base=$(git rev-parse --show-toplevel)
cd "$base"
source $base/../launch_env


pg_ctl start \
	-l $CHAFAN_BASE_DIR/pgsql_logfile   \
	-D   $CHAFAN_PG_DB_CLUSTER \
	-o "--unix_socket_directories='$CHAFAN_PG_DB_BASE'  -p $CHAFAN_PG_PORT"

pg_ctl    -D   $CHAFAN_PG_DB_CLUSTER  status

psql -h 127.0.0.1 -p  $CHAFAN_PG_PORT --list

