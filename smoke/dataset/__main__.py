#!/usr/bin/env python3
"""CLI entry point for ``python -m smoke.dataset``. See :mod:`smoke.dataset`."""
from __future__ import annotations

import argparse
import sys

from chafan_core.db.session import SessionLocal
from smoke.dataset import build, verify


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument(
        "--deep",
        action="store_true",
        help="include the answer and the Activity/Feed/Notification rows",
    )
    args = parser.parse_args()

    db = SessionLocal()
    if args.action == "build":
        data = build(db, deep=args.deep)
        print(
            f"dataset built  site={data.site.subdomain!r} question={data.question.uuid}"
        )
        print(
            f"dataset built  users={len(data.users)} questions={len(data.questions)} "
            f"answers={len(data.answers)} articles={len(data.articles)}"
        )
        if args.deep:
            print(f"dataset built  deep_answer={data.deep_answer.uuid}")
        return 0

    try:
        verify(db, deep=args.deep)
    except AssertionError as exc:
        print(f"dataset VERIFY FAILED: {exc}", file=sys.stderr)
        return 1
    print("dataset verified: intact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
