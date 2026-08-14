"""Report which uploaded images are orphans -- referenced by no body any more.

    make upload-report              # list orphans
    make upload-report-sha --sha=<sha>  # list usages of one sha (not wired to make)

Storage in the upload bucket is treated as losable; the upload table is the
recovery manifest. Orphans here are objects that no live or archived body
references any more, and are the candidates for a future garbage-collection
step. Nothing is deleted from the bucket or the table by this script.
"""

import os.path
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import argparse

from chafan_core.app import crud
from chafan_core.app.services import uploads as uploads_service
from chafan_core.db.session import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sha",
        help="print usages of a single sha instead of scanning for orphans",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.sha:
            usages = uploads_service.find_usages(db, sha=args.sha)
            for usage in usages:
                print(usage)
            print(f"{len(usages)} usage(s) for {args.sha}")
            return 0

        orphans = uploads_service.find_orphans(db)
        for upload in orphans:
            print(
                f"upload_id={upload.id} sha={upload.sha256} purpose={upload.purpose} "
                f"uploader_id={upload.uploader_id} "
                f"created_at={upload.created_at.isoformat()}"
            )
        print(
            f"{len(orphans)} orphan upload(s) across {len(crud.upload.all_shas(db))} "
            "distinct sha(s)"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
