#!/usr/bin/env python3
"""Bootstrap-mode seed for the smoke suite.

Populates a *fresh* dev database with the minimum fixtures the smoke
scenarios assume already exist against production:

  - two member accounts (A and B),
  - a public site both accounts belong to,
  - an article column owned by A,
  - one public question (the "known question" s02 reads anonymously).

then writes ``smoke/config.json`` so ``run_all.py`` can run unchanged.

This talks to the DB directly through the crud layer (same pattern as
``scripts/initial_data.py``) rather than driving the public registration
API: open-account requires an invitation link + emailed verification code,
which is friction we don't want in CI. The scenarios themselves still
exercise the HTTP API end-to-end; this only establishes preconditions.

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

from chafan_core.app import crud, schemas
from chafan_core.app import rep_manager as rep
from chafan_core.db.session import SessionLocal
from chafan_core.utils.validators import (
    StrippedNonEmptyBasicStr,
    StrippedNonEmptyStr,
)

API_BASE = os.environ.get("SMOKE_API_BASE", "http://127.0.0.1:8000")
# Generous for a cold CI runner: s10/s11 poll post-response fan-out.
POLL_TIMEOUT_SECONDS = int(os.environ.get("SMOKE_POLL_TIMEOUT_SECONDS", "60"))

SITE_SUBDOMAIN = "smoke"
SITE_NAME = "Smoke Test Site"
COLUMN_NAME = "Smoke Test Column"
KNOWN_QUESTION_TITLE = "Smoke test seed question"
# Fresh users start at 0 coins (INITIAL_USER_COINS=0), but several scenarios
# deduct coins (question/article/upvote). Grant a generous balance so the
# write paths aren't gated on coin economics.
TARGET_COINS = 1000

ACCOUNTS = {
    "account_a": {
        "email": "smoke-a@cha.fan",
        "handle": "smoke_a",
        "full_name": "Smoke A",
        "password": "smoke-pw-a1",
    },
    "account_b": {
        "email": "smoke-b@cha.fan",
        "handle": "smoke_b",
        "full_name": "Smoke B",
        "password": "smoke-pw-b1",
    },
}


def _get_or_create_user(db, spec: dict):
    user = crud.user.get_by_email(db, email=spec["email"])
    if user:
        return user
    user_in = schemas.UserCreate(
        email=spec["email"],
        password=spec["password"],
        handle=StrippedNonEmptyBasicStr(spec["handle"]),
        full_name=StrippedNonEmptyStr(spec["full_name"]),
    )
    return crud.user.create(db, obj_in=user_in)


def _ensure_coins(db, user) -> None:
    if user.remaining_coins < TARGET_COINS:
        rep.award_coins(
            db, user, TARGET_COINS - user.remaining_coins, reason="smoke seed"
        )
        db.commit()


def _get_or_create_site(db, moderator):
    site = crud.site.get_by_subdomain(db, subdomain=SITE_SUBDOMAIN)
    if site:
        return site
    site_in = schemas.SiteCreate(
        name=StrippedNonEmptyStr(SITE_NAME),
        subdomain=StrippedNonEmptyBasicStr(SITE_SUBDOMAIN),
        permission_type="public",
        description="Ephemeral site created by the bootstrap smoke seed.",
    )
    return crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )


def _ensure_membership(db, site, user):
    existing = crud.profile.get_by_user_and_site(
        db, owner_id=user.id, site_id=site.id
    )
    if existing:
        return existing
    return crud.profile.create_with_owner(
        db,
        obj_in=schemas.ProfileCreate(site_uuid=site.uuid, owner_uuid=user.uuid),
    )


def _get_or_create_column(db, owner):
    for col in getattr(owner, "article_columns", []) or []:
        if col.name == COLUMN_NAME:
            return col
    return crud.article_column.create_with_owner(
        db,
        obj_in=schemas.ArticleColumnCreate(name=StrippedNonEmptyStr(COLUMN_NAME)),
        owner_id=owner.id,
    )


def _get_or_create_known_question(db, site, author):
    existing = (
        db.query(crud.question.model)
        .filter_by(site_id=site.id, title=KNOWN_QUESTION_TITLE)
        .first()
    )
    if existing:
        return existing
    return crud.question.create_with_author(
        db,
        obj_in=schemas.QuestionCreate(
            site_uuid=site.uuid,
            title=StrippedNonEmptyStr(KNOWN_QUESTION_TITLE),
        ),
        author_id=author.id,
    )


def main() -> None:
    db = SessionLocal()

    a = _get_or_create_user(db, ACCOUNTS["account_a"])
    b = _get_or_create_user(db, ACCOUNTS["account_b"])
    _ensure_coins(db, a)
    _ensure_coins(db, b)

    site = _get_or_create_site(db, moderator=a)
    _ensure_membership(db, site, a)
    _ensure_membership(db, site, b)

    column = _get_or_create_column(db, owner=a)
    question = _get_or_create_known_question(db, site, author=a)

    config = {
        "api_base": API_BASE,
        "site": site.subdomain,
        "article_column_uuid": column.uuid,
        "known_question_uuid": question.uuid,
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

    print(f"seed OK  site={site.subdomain!r} uuid={site.uuid}")
    print(f"seed OK  column uuid={column.uuid}")
    print(f"seed OK  known question uuid={question.uuid}")
    print(f"seed OK  wrote {out}")


if __name__ == "__main__":
    main()
