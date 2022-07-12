#!/usr/bin/env bash

set -x
set -e

mypy chafan_core
black chafan_core --check
isort --recursive --check-only --skip chafan_core/e2e_tests/main.py chafan_core
flake8 chafan_core --max-line-length 99 --select=E9,E63,F7,F82
