"""Fill activity.subject_user_id from event_json for rows written before it existed.

Step 3 of docs/proposals/2026-08-04-activity-feed-reassignment.md. Step 1 added
the column empty and step 2 populates it on write, so every row predating that
deploy has a null subject. Step 4 queries subject timelines by this column with
no fallback, so those rows would simply stop appearing on profiles. This puts
them back.

Nothing new is derived. The subject is already recorded on every one of those
rows, inside event_json at content.subject_id; this lifts it into the column so
it is expressible in SQL.

Safe to interrupt, safe to re-run
---------------------------------
Only rows WHERE subject_user_id IS NULL are touched, so a second run is a no-op
over what the first one finished, and a run killed halfway leaves committed
batches done and the rest still null. event_json is never written. To undo the
whole thing: UPDATE activity SET subject_user_id = NULL.

Skips, never aborts
-------------------
A row whose payload will not parse, or whose subject_id names a user that no
longer exists, is counted and left null rather than failing the run. One
unreadable row from some retired code path must not stop the other 411. Both
outcomes are why the column is nullable.

Such rows are not marked, so every later run re-examines them -- `filled` goes
to zero on a second pass but `scanned` does not. At the size this table is,
that costs nothing and it keeps the script stateless.

Parsing happens in Python rather than as `event_json::jsonb` in SQL for that
reason: the cast raises on the first malformed row and takes the whole
statement with it, and pg_input_is_valid is PostgreSQL 16+ (production is 14).

Usage
-----
    python scripts/backfill_activity_subject.py --dry-run
    python scripts/backfill_activity_subject.py

Run it *after* deploying the step-2 code, or run it again afterwards: anything
written while the old code is still live lands with a null subject.
"""

import os.path
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import argparse
import json
import logging
from collections import Counter
from typing import List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("backfill_activity_subject")

DEFAULT_BATCH_SIZE = 1000


def subject_id_of(event_json: Optional[str]) -> Optional[int]:
    """The subject recorded in a payload, or None if it cannot be read.

    Tolerant on purpose -- a payload that is not JSON, not an object, missing
    content, missing subject_id, or carrying a non-integer one all yield None
    and are skipped by the caller.
    """
    try:
        content = json.loads(event_json or "")["content"]
    except Exception:
        return None
    if not isinstance(content, dict):
        return None
    subject_id = content.get("subject_id")
    return subject_id if isinstance(subject_id, int) else None


def _existing_user_ids(db: Session, user_ids: Set[int]) -> Set[int]:
    if not user_ids:
        return set()
    rows = db.query(models.User.id).filter(models.User.id.in_(user_ids)).all()
    return {row[0] for row in rows}


def backfill(
    db: Session, *, batch_size: int = DEFAULT_BATCH_SIZE, dry_run: bool = False
) -> Counter:
    """Walk the null-subject rows in id order, filling what can be resolved."""
    stats: Counter = Counter()
    after_id = 0

    while True:
        batch: List[models.Activity] = (
            db.query(models.Activity)
            .filter(
                models.Activity.subject_user_id.is_(None),
                models.Activity.id > after_id,
            )
            .order_by(models.Activity.id)
            .limit(batch_size)
            .all()
        )
        if not batch:
            break
        after_id = batch[-1].id

        pending: List[Tuple[models.Activity, int]] = []
        for activity in batch:
            stats["scanned"] += 1
            subject_id = subject_id_of(activity.event_json)
            if subject_id is None:
                stats["skipped_unreadable"] += 1
                logger.warning("activity %s: no readable subject", activity.id)
                continue
            pending.append((activity, subject_id))

        # One lookup per batch rather than one per row: the subjects repeat.
        live_user_ids = _existing_user_ids(db, {sid for _, sid in pending})
        # A SAVEPOINT rather than a plain rollback for --dry-run: this function
        # is handed a Session it does not own, and undoing the caller's other
        # uncommitted work to unwind our own would be a surprising thing for a
        # dry run to do.
        savepoint = db.begin_nested()
        for activity, subject_id in pending:
            if subject_id not in live_user_ids:
                stats["skipped_missing_user"] += 1
                logger.warning(
                    "activity %s: subject %s no longer exists", activity.id, subject_id
                )
                continue
            activity.subject_user_id = subject_id
            stats["filled"] += 1

        db.flush()
        if dry_run:
            savepoint.rollback()
        else:
            savepoint.commit()
            db.commit()
        logger.info(
            "scanned %s rows so far (through id %s)", stats["scanned"], after_id
        )

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change, then roll back without writing",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        remaining_before = (
            db.query(models.Activity)
            .filter(models.Activity.subject_user_id.is_(None))
            .count()
        )
        logger.info(
            "%s activities have no subject%s",
            remaining_before,
            " (dry run: nothing will be written)" if args.dry_run else "",
        )
        stats = backfill(db, batch_size=args.batch_size, dry_run=args.dry_run)
        logger.info(
            "scanned=%s filled=%s skipped_unreadable=%s skipped_missing_user=%s",
            stats["scanned"],
            stats["filled"],
            stats["skipped_unreadable"],
            stats["skipped_missing_user"],
        )
        if not args.dry_run:
            remaining_after = (
                db.query(models.Activity)
                .filter(models.Activity.subject_user_id.is_(None))
                .count()
            )
            logger.info("%s activities still have no subject", remaining_after)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
