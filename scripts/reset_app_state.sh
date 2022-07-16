set -e
set -x

redis-cli flushall
psql -h localhost -p 5432 -U postgres -c 'drop database chafan_dev WITH (FORCE);'
psql -h localhost -p 5432 -U postgres -c 'create database chafan_dev;'
alembic upgrade head
python scripts/initial_data.py
