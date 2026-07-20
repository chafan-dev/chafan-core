#!/usr/bin/env bash

set -xe

# Architecture ratchet (must pass).
python scripts/static_analysis/check_layer_imports.py

mypy chafan_core || true
black chafan_core --check || true
isort --check-only --skip chafan_core/e2e_tests/main.py chafan_core || true
flake8 chafan_core --max-line-length 99 --select=E9,E63,F7,F82
