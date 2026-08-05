#!/usr/bin/env python3
"""The shared development dataset: build it, then assert it survived.

One definition of "a database with realistic rows in it", used by two callers
that both need one and would otherwise each grow their own:

- ``smoke/seed.py`` builds it as the precondition for the e2e smoke suite,
  then writes ``smoke/config.json`` so the scenarios can find their fixtures.
- the ``Migrations`` workflow builds it, migrates across it, and calls
  :func:`verify` to prove the migration preserved it.

That second caller is why :func:`verify` re-queries by stable identifiers --
email, subdomain, title -- rather than by id or by anything held in memory. It
runs in a separate process from the build, after the schema underneath the
rows has changed.

Idempotent throughout: every ``_get_or_create_*`` reuses an existing row, so
building twice is a no-op and a partially-seeded database converges.

Usage::

    PYTHONPATH=$PWD python -m smoke.dataset build [--deep]
    PYTHONPATH=$PWD python -m smoke.dataset verify [--deep]
"""
from __future__ import annotations

import argparse
import datetime
import sys
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv  # isort:skip

load_dotenv()  # isort:skip

from chafan_core.app import crud, models, schemas
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.event import (
    AnswerQuestionInternal,
    CreateQuestionInternal,
    EventInternal,
)
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.services import events
from chafan_core.app.services import reputation as rep
from chafan_core.db.session import SessionLocal
from chafan_core.utils.base import ContentVisibility, get_uuid
from chafan_core.utils.validators import (
    StrippedNonEmptyBasicStr,
    StrippedNonEmptyStr,
)

SITE_SUBDOMAIN = "smoke"
SITE_NAME = "Smoke Test Site"
COLUMN_NAME = "Smoke Test Column"
KNOWN_QUESTION_TITLE = "Smoke test seed question"
KNOWN_ANSWER_BODY = "Smoke test seed answer body."

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


@dataclass
class Dataset:
    """What a build produced, for callers that need the ids."""

    account_a: models.User
    account_b: models.User
    site: models.Site
    column: models.ArticleColumn
    question: models.Question
    answer: Optional[models.Answer] = None


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


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
    existing = crud.profile.get_by_user_and_site(db, owner_id=user.id, site_id=site.id)
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
        db.query(models.Question)
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


def _get_or_create_known_answer(db, question, author):
    existing = (
        db.query(models.Answer)
        .filter_by(question_id=question.id, author_id=author.id)
        .first()
    )
    if existing:
        return existing
    return crud.answer.create_with_author(
        db,
        obj_in=schemas.AnswerCreate(
            question_uuid=question.uuid,
            content=RichText(
                source=KNOWN_ANSWER_BODY,
                editor="tiptap",
                rendered_text=KNOWN_ANSWER_BODY,
            ),
            is_published=True,
            visibility=ContentVisibility.ANYONE,
            writing_session_uuid=get_uuid(),
        ),
        author_id=author.id,
        site_id=question.site_id,
    )


def _build_deep(db, data: Dataset) -> Dataset:
    """The rows a migration is most likely to disturb: events and their sinks.

    Built through ``events.distribute`` rather than by hand, so the Activity,
    Feed and Notification rows are shaped exactly as the application makes
    them. B follows A first, so the fan-out has somewhere to go -- without a
    follower there would be no Feed rows and this would prove nothing.
    """
    crud.user.add_follower(db, db_obj=data.account_a, follower=data.account_b)

    data.answer = _get_or_create_known_answer(db, data.question, author=data.account_b)
    db.flush()

    ctx = RequestContext()
    ctx.db = db
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    if not _activities_for_verb(db, "create_question"):
        events.distribute(
            ctx,
            EventInternal(
                created_at=now,
                content=CreateQuestionInternal(
                    subject_id=data.account_a.id, question_id=data.question.id
                ),
            ),
        )
    if not _activities_for_verb(db, "answer_question"):
        events.distribute(
            ctx,
            EventInternal(
                created_at=now,
                content=AnswerQuestionInternal(
                    subject_id=data.account_b.id, answer_id=data.answer.id
                ),
            ),
        )
    return data


def _activities_for_verb(db, verb: str) -> list:
    return [
        a
        for a in db.query(models.Activity).all()
        if f'"verb": "{verb}"' in str(a.event_json)
        or f'"verb":"{verb}"' in str(a.event_json)
    ]


def build(db, *, deep: bool = False) -> Dataset:
    """Create (or reuse) the dataset. Commits.

    ``deep`` adds an answer plus the Activity/Feed/Notification rows that flow
    from distributing its event. The smoke suite does not want those -- its
    scenarios create their own and assert on what they find -- so it stays off
    by default and the migration job turns it on.
    """
    a = _get_or_create_user(db, ACCOUNTS["account_a"])
    b = _get_or_create_user(db, ACCOUNTS["account_b"])
    _ensure_coins(db, a)
    _ensure_coins(db, b)

    site = _get_or_create_site(db, moderator=a)
    _ensure_membership(db, site, a)
    _ensure_membership(db, site, b)

    column = _get_or_create_column(db, owner=a)
    question = _get_or_create_known_question(db, site, author=a)
    db.flush()

    data = Dataset(
        account_a=a, account_b=b, site=site, column=column, question=question
    )
    if deep:
        data = _build_deep(db, data)

    db.commit()
    return data


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify(db, *, deep: bool = False) -> None:
    """Assert the dataset is intact. Raises AssertionError with the detail.

    Checks content, not just row counts: a migration that drops a column or
    mangles a value leaves the count untouched. Relationships are dereferenced
    for the same reason -- a broken foreign key survives a count.
    """
    a = crud.user.get_by_email(db, email=ACCOUNTS["account_a"]["email"])
    b = crud.user.get_by_email(db, email=ACCOUNTS["account_b"]["email"])
    _require(a is not None, "account_a is gone")
    _require(b is not None, "account_b is gone")
    _require(
        a.handle == ACCOUNTS["account_a"]["handle"],
        f"account_a.handle changed: {a.handle!r}",
    )
    _require(
        a.remaining_coins >= TARGET_COINS,
        f"account_a lost coins: {a.remaining_coins}",
    )
    _require(a.hashed_password not in (None, ""), "account_a lost its password hash")

    site = crud.site.get_by_subdomain(db, subdomain=SITE_SUBDOMAIN)
    _require(site is not None, "site is gone")
    _require(site.name == SITE_NAME, f"site.name changed: {site.name!r}")
    _require(site.moderator_id == a.id, "site lost its moderator FK")

    for user in (a, b):
        profile = crud.profile.get_by_user_and_site(
            db, owner_id=user.id, site_id=site.id
        )
        _require(profile is not None, f"membership for {user.handle} is gone")

    question = (
        db.query(models.Question)
        .filter_by(site_id=site.id, title=KNOWN_QUESTION_TITLE)
        .first()
    )
    _require(question is not None, "known question is gone")
    _require(question.author_id == a.id, "question lost its author FK")
    _require(question.site.subdomain == SITE_SUBDOMAIN, "question lost its site FK")

    column = next(
        (c for c in (a.article_columns or []) if c.name == COLUMN_NAME), None
    )
    _require(column is not None, "article column is gone")

    if not deep:
        return

    answer = (
        db.query(models.Answer).filter_by(question_id=question.id, author_id=b.id).first()
    )
    _require(answer is not None, "known answer is gone")
    _require(
        KNOWN_ANSWER_BODY in str(answer.body), f"answer body changed: {answer.body!r}"
    )

    _require(a in b.followed, "the follow edge is gone")

    for verb in ("create_question", "answer_question"):
        activities = _activities_for_verb(db, verb)
        _require(activities, f"no Activity survived for {verb}")
        for activity in activities:
            _require(
                activity.event_json not in (None, ""),
                f"{verb} Activity lost its payload",
            )

    feeds = db.query(models.Feed).count()
    _require(feeds > 0, "every Feed row is gone")
    for feed in db.query(models.Feed).all():
        _require(feed.activity is not None, "a Feed row lost its Activity FK")

    notifications = db.query(models.Notification).count()
    _require(notifications > 0, "every Notification row is gone")


# ---------------------------------------------------------------------------


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
        print(f"dataset built  site={data.site.subdomain!r} question={data.question.uuid}")
        if args.deep:
            print(f"dataset built  answer={data.answer.uuid}")
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
