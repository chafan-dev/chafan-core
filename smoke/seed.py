#!/usr/bin/env python3
"""Bootstrap-mode seed for the smoke suite.

Builds the shared development dataset (:mod:`smoke.dataset`) and writes
``smoke/config.json`` so ``run_all.py`` can run unchanged. The rows themselves
are defined in that module, because the ``Migrations`` workflow needs the same
ones to test that a migration preserves data.

The dataset talks to the DB directly through the crud layer (same pattern as
``scripts/initial_data.py``) rather than driving the public registration API:
open-account requires an invitation link + emailed verification code, which is
friction we don't want in CI. The scenarios themselves still exercise the HTTP
API end-to-end; this only establishes preconditions.

Run from the repo root with the app importable, e.g.::

    PYTHONPATH=$PWD python smoke/seed.py

Idempotent: existing rows (by email / subdomain) are reused, so a re-run
against an already-seeded DB is a no-op that still rewrites config.json.
"""
from __future__ import annotations

import json
import os
import pathlib

from dotenv import load_dotenv  # isort:skip

load_dotenv()  # isort:skip

from chafan_core.db.session import SessionLocal
from smoke.dataset import ACCOUNTS, build

API_BASE = os.environ.get("SMOKE_API_BASE", "http://127.0.0.1:8000")
# Generous for a cold CI runner: s10/s11 poll post-response fan-out.
POLL_TIMEOUT_SECONDS = int(os.environ.get("SMOKE_POLL_TIMEOUT_SECONDS", "60"))


def main() -> None:
    db = SessionLocal()

    # deep=False: the scenarios create their own answers, activities and
    # notifications and assert on what they find. Pre-seeding those would be
    # noise they have to work around.
    data = build(db, deep=False)

    config = {
        "api_base": API_BASE,
        "site": data.site.subdomain,
        "article_column_uuid": data.column.uuid,
        "known_question_uuid": data.question.uuid,
        "poll_timeout_seconds": POLL_TIMEOUT_SECONDS,
        "account_a": {
            "username": ACCOUNTS["account_a"]["email"],
            "password": ACCOUNTS["account_a"]["password"],
        },
        "account_b": {
            "username": ACCOUNTS["account_b"]["email"],
            "password": ACCOUNTS["account_b"]["password"],
        },
    }

    out = pathlib.Path(__file__).resolve().parent / "config.json"
    out.write_text(json.dumps(config, indent=2) + "\n")

    print(f"seed OK  site={data.site.subdomain!r} uuid={data.site.uuid}")
    print(f"seed OK  column uuid={data.column.uuid}")
    print(f"seed OK  known question uuid={data.question.uuid}")
    print(f"seed OK  wrote {out}")


if __name__ == "__main__":
    main()
