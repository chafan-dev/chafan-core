#!/usr/bin/env python3
"""Ratchet: every rule in `rules.py` must actually be applied somewhere.

Run: python scripts/static_analysis/check_rules_applied.py

A rule that is declared but never read is a hanging rule -- it reads like a
promise the site makes and enforces nothing. Chafan had two of these for years:
a coin cost for writing an article that was checked against your balance but
never charged, and a karma threshold for creating a private site that no code
path could ever unlock.

This check fails if a name in `rules.py` has no reader outside that file, so
the next one cannot be added silently. Deleting a rule you do not want to apply
is always a valid fix.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "chafan_core" / "app" / "rules.py"


def declared_rules() -> list[str]:
    tree = ast.parse(RULES.read_text(), filename=str(RULES))
    return [
        node.targets[0].id
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id.isupper()
    ]


def readers(name: str) -> list[str]:
    """Files that read `rules.<name>` (or import the bare name from rules)."""
    hits = []
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or path == RULES:
            continue
        text = path.read_text(errors="ignore")
        if f"rules.{name}" in text or f"import {name}" in text:
            hits.append(str(path.relative_to(ROOT)))
    return hits


def main() -> int:
    unapplied = [name for name in declared_rules() if not readers(name)]
    for name in unapplied:
        print(
            f"ERROR chafan_core/app/rules.py: {name} is declared but never applied",
            file=sys.stderr,
        )
    total = len(declared_rules())
    print(f"rules-applied check: {total - len(unapplied)}/{total} rules applied")
    return 1 if unapplied else 0


if __name__ == "__main__":
    sys.exit(main())
