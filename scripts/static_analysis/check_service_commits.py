#!/usr/bin/env python3
"""Ratchet: one transaction boundary per use case.

Run: python scripts/static_analysis/check_service_commits.py

`api/`, `services/` and `crud/` must never call `.commit()`. They do
`db.add()`/`db.flush()` and let the caller's boundary commit once:

  - HTTP requests      api/deps.py get_request_context{,_logged_in} / get_db
  - background/cron    infra/runtime.py execute_with_context / execute_with_db

A commit in the middle of a use case splits it into two transactions, and
neither boundary can roll back past the first one. That is how rejected
question and submission edits came to leave orphan archive rows: validation
raised *after* the archive had already been made durable.

Two exemptions, deliberately kept separate:

  - BOUNDARY_FILES are the commit boundaries themselves. Permanent.
  - ALLOWLIST is migration debt. Entries may only be removed, never added,
    and an entry that no longer commits is an error so it cannot linger and
    silently re-permit a commit later.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "chafan_core"

# Directories that must not commit, relative to chafan_core/.
GUARDED_DIRS = ("app/services", "app/crud", "app/api")

# The boundaries themselves: these are where the single commit belongs.
BOUNDARY_FILES = {
    "chafan_core/app/api/deps.py",
}

# Files permitted to keep a commit, keyed by path rather than path:line so a
# moved line cannot silently re-arm the exemption. Must only ever shrink.
ALLOWLIST: set[str] = {
    # Mid-migration: the last endpoint holding business logic. It also sits
    # on check_layer_imports.py's allowlist; clearing it clears both.
    "chafan_core/app/api/api_v1/endpoints/login.py",
}


def iter_py_files(base: Path):
    for path in base.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def is_guarded(path: Path) -> bool:
    if str(path.relative_to(ROOT.parent)) in BOUNDARY_FILES:
        return False
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

    `ctx`/`context` counts too: RequestContext.commit() is a transaction
    boundary, and endpoints increasingly hold a ctx rather than a raw session,
    so `ctx.commit()` is the form a regression would most likely take.

    Deliberately excludes non-SQLAlchemy commits that share the method name --
    `writer.commit()` on a Whoosh IndexWriter in services/search.py is not a
    transaction boundary.
    """
    lowered = name.lower()
    return any(tok in lowered for tok in ("db", "session", "ctx", "context"))


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

    used_allowlist: set[str] = set()

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
                f"{rel}:{lineno}: api/services/crud must not commit; "
                f"let the request or background boundary commit once"
            )
            if str(rel) in ALLOWLIST:
                used_allowlist.add(str(rel))
                warnings.append(msg + " (allowlisted)")
            else:
                errors.append(msg)

    # An entry that no longer commits must go, or it silently re-permits one.
    for entry in sorted(ALLOWLIST - used_allowlist):
        errors.append(f"{entry}: allowlist entry no longer commits; remove it")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)

    print(f"service-commit check: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
