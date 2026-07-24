#!/usr/bin/env python3
"""Ratchet: one transaction boundary per use case.

Run: python scripts/static_analysis/check_service_commits.py

`services/` and `crud/` must never call `.commit()`. They do `db.add()`/
`db.flush()` and let the caller's boundary commit once:

  - HTTP requests      api/deps.py get_request_context{,_logged_in} / get_db
  - background/cron    infra/runtime.py execute_with_context / execute_with_db

A commit in the middle of a service function splits the use case into two
transactions, and neither boundary can roll back past the first one. That is
how rejected question and submission edits came to leave orphan archive rows:
validation raised *after* the archive had already been made durable.

ALLOWLIST is empty and entries may only be removed, never added.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "chafan_core"

# Directories that must not commit, relative to chafan_core/.
GUARDED_DIRS = ("app/services", "app/crud")

# Files permitted to keep a commit, keyed by path rather than path:line so a
# moved line cannot silently re-arm the exemption. Must only ever shrink.
ALLOWLIST: set[str] = set()


def iter_py_files(base: Path):
    for path in base.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def is_guarded(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(rel.startswith(d + "/") for d in GUARDED_DIRS)


def receiver_name(node: ast.expr) -> str:
    """Best-effort name of whatever `.commit()` was called on."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return receiver_name(node.func) + "()"
    return "<expr>"


def is_db_receiver(name: str) -> bool:
    """True for session-like receivers: db, write_db, get_db(), session, ...

    Deliberately excludes non-SQLAlchemy commits that share the method name --
    `writer.commit()` on a Whoosh IndexWriter in services/search.py is not a
    transaction boundary.
    """
    lowered = name.lower()
    return "db" in lowered or "session" in lowered


def commit_calls(path: Path) -> list[tuple[int, str]]:
    """(line, receiver) for every `<x>.commit()` call in the file."""
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as e:
        print(f"SYNTAX {path}: {e}", file=sys.stderr)
        return []
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "commit"
        ):
            out.append((node.lineno, receiver_name(node.func.value)))
    return out


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for path in sorted(iter_py_files(ROOT)):
        if not is_guarded(path):
            continue
        rel = path.relative_to(ROOT.parent)
        for lineno, receiver in commit_calls(path):
            if not is_db_receiver(receiver):
                warnings.append(
                    f"{rel}:{lineno}: {receiver}.commit() ignored (not a db session)"
                )
                continue
            msg = (
                f"{rel}:{lineno}: services/crud must not commit; "
                f"let the request or background boundary commit once"
            )
            if str(rel) in ALLOWLIST:
                warnings.append(msg + " (allowlisted)")
            else:
                errors.append(msg)

    stale = sorted(
        entry
        for entry in ALLOWLIST
        if not any(
            str(p.relative_to(ROOT.parent)) == entry for p in iter_py_files(ROOT)
        )
    )
    for entry in stale:
        warnings.append(f"{entry}: allowlist entry no longer exists; remove it")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)

    print(f"service-commit check: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
