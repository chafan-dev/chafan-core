"""Recompute every active user's karma from scratch and write it back.

    python scripts/refresh_karmas.py            # show what would change, write nothing
    python scripts/refresh_karmas.py --apply    # write the recomputed values

Karma is normally applied the moment it is earned (see `chafan_core/app/karma.py`),
so a healthy run reports no drift at all. Run this:

  * after changing a number in `chafan_core/app/rules.py`, to apply the new rule
    to karma that was already earned under the old one; and
  * when you suspect a state change is not being tracked -- any drift reported
    here is a mutation path that forgot to go through `karma.tracked()`.
"""

import os.path
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import argparse
import logging

from chafan_core.app import crud, karma
from chafan_core.db.session import SessionLocal

logging.basicConfig(level=logging.WARNING)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the recomputed values (default: report only)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        drifted = 0
        users = crud.user.get_all_active_users(db)
        for user in users:
            stored = user.karma or 0
            computed = karma.compute_karma(db, user)
            if computed == stored:
                continue
            drifted += 1
            print(
                f"user_id={user.id} handle={user.handle} "
                f"stored={stored} computed={computed} drift={computed - stored:+d}"
            )
            if args.apply:
                karma.set_karma(db, user, computed)
        if args.apply:
            db.commit()
        print(
            f"{len(users)} active user(s), {drifted} drifted"
            + (", written" if args.apply else ", nothing written (pass --apply)")
        )
        # Drift is a bug report, not routine maintenance: fail loudly so a CI
        # or cron caller notices a mutation path that skipped karma.tracked().
        return 1 if drifted else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
