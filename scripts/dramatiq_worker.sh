#! /usr/bin/env bash
set -e

export dramatiq_prom_host=0.0.0.0
export dramatiq_prom_port=9191
export prometheus_multiproc_dir=/tmp/dramatiq-prometheus
export dramatiq_prom_db=$prometheus_multiproc_dir
export DB_SESSION_POOL_SIZE=2
export DB_SESSION_POOL_MAX_OVERFLOW_SIZE=1

mkdir -p $prometheus_multiproc_dir

dramatiq --threads 2 chafan_core.app.task
