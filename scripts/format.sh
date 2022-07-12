#!/bin/sh -e
set -x

autoflake --remove-all-unused-imports --recursive --remove-unused-variables --in-place chafan_core --exclude=__init__.py
black chafan_core
isort --recursive --apply chafan_core
