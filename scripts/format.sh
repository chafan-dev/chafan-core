#!/bin/sh -e
set -x

isort --force-single-line-imports chafan_core
autoflake --remove-all-unused-imports --recursive --remove-unused-variables --in-place chafan_core --exclude=__init__.py
black chafan_core
isort chafan_core
