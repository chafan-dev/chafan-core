#!/usr/bin/env bash

set -xe

mypy chafan_core
black chafan_core --check
isort --check-only --skip chafan_core/tests chafan_core
flake8 chafan_core --max-line-length 99 --select=E9,E63,F7,F82
