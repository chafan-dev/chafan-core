#! /usr/bin/env bash
set -e

export dramatiq_prom_host=0.0.0.0
export dramatiq_prom_port=9191
export prometheus_multiproc_dir=/tmp/dramatiq-prometheus
export dramatiq_prom_db=$prometheus_multiproc_dir

mkdir -p $prometheus_multiproc_dir

dramatiq chafan_core.app.task
