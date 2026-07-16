#!/usr/bin/env python3
"""Ratchet: enforce downward-only import rules between layers.

Run: python scripts/static_analysis/check_layer_imports.py

Currently enforced (must stay clean):
  - no imports of deleted modules (data_broker, materialize, task_utils, cached_layer)
  - responders must not import services
  - crud must not import services, responders, or api

Reported as warnings (migration still in progress):
  - api endpoints importing crud or responders directly
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "chafan_core"

DEAD_MODULES = (
    "chafan_core.app.data_broker",
    "chafan_core.app.materialize",
    "chafan_core.app.task_utils",
    "chafan_core.app.cached_layer",
)


def iter_py_files(base: Path):
    for path in base.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def module_imports(path: Path) -> list[tuple[str, int]]:
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as e:
        print(f"SYNTAX {path}: {e}", file=sys.stderr)
        return []
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.module, node.lineno))
            # also record submodule names for "from chafan_core.app import crud"
            if node.module == "chafan_core.app":
                for alias in node.names:
                    out.append((f"chafan_core.app.{alias.name}", node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, node.lineno))
    return out


def layer_of(path: Path) -> str:
    s = path.as_posix()
    if "/api/api_v1/endpoints/" in s:
        return "api"
    if "/services/" in s:
        return "services"
    if "/responders/" in s:
        return "responders"
    if "/crud/" in s:
        return "crud"
    if "/infra/" in s:
        return "infra"
    return "other"


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for path in iter_py_files(ROOT):
        layer = layer_of(path)
        rel = path.relative_to(ROOT.parent)
        for mod, lineno in module_imports(path):
            if not mod.startswith("chafan_core"):
                continue

            if any(mod == d or mod.startswith(d + ".") for d in DEAD_MODULES):
                errors.append(f"{rel}:{lineno}: import of deleted module {mod}")

            if layer == "responders" and (
                mod.startswith("chafan_core.app.services")
                or mod == "chafan_core.app.services"
            ):
                errors.append(f"{rel}:{lineno}: responders must not import services ({mod})")

            if layer == "crud" and (
                mod.startswith("chafan_core.app.services")
                or mod.startswith("chafan_core.app.responders")
                or mod.startswith("chafan_core.app.api")
            ):
                errors.append(f"{rel}:{lineno}: crud must not import {mod}")

            if layer == "api" and (
                mod == "chafan_core.app.crud"
                or mod.startswith("chafan_core.app.crud.")
                or mod.startswith("chafan_core.app.responders")
            ):
                warnings.append(
                    f"{rel}:{lineno}: api still imports {mod} (migrate to services)"
                )
            # from chafan_core.app import crud
            if layer == "api" and mod == "chafan_core.app.crud":
                pass  # already covered

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)

    print(
        f"layer-import check: {len(errors)} error(s), {len(warnings)} warning(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
