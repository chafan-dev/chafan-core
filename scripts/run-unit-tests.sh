#!/usr/bin/env bash

set -e
set -x

pytest -vv chafan_core/tests "${@}"
