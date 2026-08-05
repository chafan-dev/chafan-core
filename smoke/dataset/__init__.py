#!/usr/bin/env python3
"""The shared development dataset: build it, then assert it survived.

One definition of "a database with realistic rows in it", used by two callers
that both need one and would otherwise each grow their own:

- ``smoke/seed.py`` builds it as the precondition for the e2e smoke suite,
  then writes ``smoke/config.json`` so the scenarios can find their fixtures.
- the ``Migrations`` workflow builds it, migrates across it, and calls
  :func:`verify` to prove the migration preserved it.

The rows themselves live in :mod:`smoke.dataset.models` -- users, a site with
three columns, questions/answers/articles, and the follow/upvote/comment
graph between them -- built through the ``build_*``/``create_*``/``upvote_*``
functions in that package. This module wires them together and owns the two
things that make it a *dataset* rather than a pile of factories: an
idempotent :func:`build` and a :func:`verify` that re-derives its
expectations from the same factory definitions.

That's why :func:`verify` re-queries by stable identifiers -- email,
subdomain, title -- rather than by id or by anything held in memory. It runs
in a separate process from the build, after the schema underneath the rows
has changed.

Idempotent throughout: every ``_get_or_create_*`` (in the factories) reuses
an existing row, so building twice is a no-op and a partially-seeded database
converges.

Usage::

    PYTHONPATH=$PWD python -m smoke.dataset build [--deep]
    PYTHONPATH=$PWD python -m smoke.dataset verify [--deep]
"""
from __future__ import annotations

import datetime

from dotenv import load_dotenv  # isort:skip

load_dotenv()  # isort:skip

from chafan_core.app import crud
from chafan_core.app import models as app_models
from chafan_core.app import schemas
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.event import (
    AnswerQuestionInternal,
    CreateQuestionInternal,
    EventInternal,
)
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.services import events
from chafan_core.utils.base import ContentVisibility, get_uuid
from smoke.dataset.models import (
    content_factory,
    interaction_factory,
    site_factory,
    user_factory,
)
from smoke.dataset.models.dataset import Dataset

TARGET_COINS = user_factory.TARGET_COINS
SITE_SUBDOMAIN = site_factory.SITE_SUBDOMAIN
SITE_NAME = site_factory.SITE_NAME

# The one question/author pair build(deep=True) attaches an extra answer and
# an Activity/Feed/Notification trail to, to prove those survive a migration.
DEEP_QUESTION_KEY = "question_a"
DEEP_ANSWER_BODY = "Smoke test deep-flow answer body."

ACCOUNTS = {u["key"]: u for u in user_factory.USERS}


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def _get_or_create_deep_answer(db, question, author):
    existing = (
        db.query(app_models.Answer)
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
                source=DEEP_ANSWER_BODY,
                editor="tiptap",
                rendered_text=DEEP_ANSWER_BODY,
            ),
            is_published=True,
            visibility=ContentVisibility.ANYONE,
            writing_session_uuid=get_uuid(),
        ),
        author_id=author.id,
        site_id=question.site_id,
    )


def _activities_for_verb(db, verb: str) -> list:
    return [
        a
        for a in db.query(app_models.Activity).all()
        if f'"verb": "{verb}"' in str(a.event_json)
        or f'"verb":"{verb}"' in str(a.event_json)
    ]


def _build_deep(db, data: Dataset) -> Dataset:
    """The rows a migration is most likely to disturb: events and their sinks.

    Built through ``events.distribute`` rather than by hand, so the Activity,
    Feed and Notification rows are shaped exactly as the application makes
    them. B follows A first, so the fan-out has somewhere to go -- without a
    follower there would be no Feed rows and this would prove nothing.
    """
    crud.user.add_follower(db, db_obj=data.account_a, follower=data.account_b)

    data.deep_answer = _get_or_create_deep_answer(
        db, data.question, author=data.account_b
    )
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
                    subject_id=data.account_b.id, answer_id=data.deep_answer.id
                ),
            ),
        )
    return data


def build(db, *, deep: bool = False) -> Dataset:
    """Create (or reuse) the dataset. Commits.

    ``deep`` adds an answer plus the Activity/Feed/Notification rows that flow
    from distributing its event. The smoke suite does not want those -- its
    scenarios create their own and assert on what they find -- so it stays off
    by default and the migration job turns it on.
    """
    users = user_factory.build_users(db)
    site, columns = site_factory.build_site_and_columns(db, users)
    questions = content_factory.create_questions(db, users, site)
    answers = content_factory.create_answers(db, users, questions)
    articles = content_factory.create_articles(db, users, columns)

    interaction_factory.build_follows(db, users)
    interaction_factory.upvote_questions(db, users, questions)
    interaction_factory.upvote_answers(db, users, answers)
    interaction_factory.upvote_articles(db, users, articles)
    interaction_factory.create_comments(db, users, questions, articles)

    data = Dataset(
        users=users,
        site=site,
        columns=columns,
        questions=questions,
        answers=answers,
        articles=articles,
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


def _verify_users(db) -> dict:
    """Re-query every seeded user by email. Returns key -> User."""
    users = {}
    for spec in user_factory.USERS:
        user = crud.user.get_by_email(db, email=spec["email"])
        _require(user is not None, f"user {spec['key']} ({spec['email']}) is gone")
        _require(
            user.handle == spec["handle"],
            f"{spec['key']}.handle changed: {user.handle!r}",
        )
        _require(
            user.remaining_coins >= TARGET_COINS,
            f"{spec['key']} lost coins: {user.remaining_coins}",
        )
        _require(
            user.hashed_password not in (None, ""),
            f"{spec['key']} lost its password hash",
        )
        _require(
            user.personal_introduction == spec["bio"],
            f"{spec['key']}.personal_introduction changed: {user.personal_introduction!r}",
        )
        users[spec["key"]] = user
    return users


def _verify_site(db, users: dict):
    site = crud.site.get_by_subdomain(db, subdomain=SITE_SUBDOMAIN)
    _require(site is not None, "site is gone")
    _require(site.name == SITE_NAME, f"site.name changed: {site.name!r}")
    _require(site.moderator_id == users["account_a"].id, "site lost its moderator FK")

    for key, user in users.items():
        profile = crud.profile.get_by_user_and_site(
            db, owner_id=user.id, site_id=site.id
        )
        _require(profile is not None, f"membership for {key} is gone")
    return site


def _verify_columns(db, users: dict) -> dict:
    owner = users["account_a"]
    columns = {}
    for spec in site_factory.COLUMNS:
        column = next(
            (c for c in (owner.article_columns or []) if c.name == spec["name"]),
            None,
        )
        _require(column is not None, f"article column {spec['key']} is gone")
        columns[spec["key"]] = column
    return columns


def _verify_questions(db, users: dict, site) -> dict:
    questions = {}
    for q in content_factory.QUESTIONS:
        question = (
            db.query(app_models.Question)
            .filter_by(site_id=site.id, title=q["title"])
            .first()
        )
        _require(question is not None, f"question {q['key']} is gone")
        _require(
            question.author_id == users[q["author"]].id,
            f"question {q['key']} lost its author FK",
        )
        _require(
            question.site.subdomain == SITE_SUBDOMAIN,
            f"question {q['key']} lost its site FK",
        )
        questions[q["key"]] = question
    return questions


def _verify_answers(db, users: dict, questions: dict) -> dict:
    answers = {}
    for a in content_factory.ANSWERS:
        question = questions[a["question"]]
        author = users[a["author"]]
        answer = (
            db.query(app_models.Answer)
            .filter_by(question_id=question.id, author_id=author.id)
            .first()
        )
        _require(answer is not None, f"answer {a['key']} is gone")
        _require(a["body"] in str(answer.body), f"answer {a['key']} body changed")
        answers[a["key"]] = answer
    return answers


def _verify_articles(db, columns: dict) -> dict:
    articles = {}
    for art in content_factory.ARTICLES:
        column = columns[art["column"]]
        article = (
            db.query(app_models.Article)
            .filter_by(article_column_id=column.id, title=art["title"])
            .first()
        )
        _require(article is not None, f"article {art['key']} is gone")
        articles[art["key"]] = article
    return articles


def _verify_follows(users: dict) -> None:
    for target_key, follower_key in interaction_factory.FOLLOWS:
        target = users[target_key]
        follower = users[follower_key]
        _require(
            target in follower.followed,
            f"follow edge {follower_key} -> {target_key} is gone",
        )


def _verify_upvotes(
    db, users: dict, questions: dict, answers: dict, articles: dict
) -> None:
    for key, voter_key in interaction_factory.QUESTION_UPVOTES:
        upvote = (
            db.query(app_models.QuestionUpvotes)
            .filter_by(question_id=questions[key].id, voter_id=users[voter_key].id)
            .first()
        )
        _require(
            upvote is not None and not upvote.cancelled,
            f"question upvote {voter_key} -> {key} is gone",
        )
    for key, voter_key in interaction_factory.ANSWER_UPVOTES:
        upvote = (
            db.query(app_models.Answer_Upvotes)
            .filter_by(answer_id=answers[key].id, voter_id=users[voter_key].id)
            .first()
        )
        _require(
            upvote is not None and not upvote.cancelled,
            f"answer upvote {voter_key} -> {key} is gone",
        )
    for key, voter_key in interaction_factory.ARTICLE_UPVOTES:
        upvote = (
            db.query(app_models.ArticleUpvotes)
            .filter_by(article_id=articles[key].id, voter_id=users[voter_key].id)
            .first()
        )
        _require(
            upvote is not None and not upvote.cancelled,
            f"article upvote {voter_key} -> {key} is gone",
        )


def _verify_comments(db, users: dict, questions: dict, articles: dict) -> None:
    for c in interaction_factory.COMMENTS:
        author = users[c["author"]]
        if "question" in c:
            parent = questions[c["question"]]
            comment = (
                db.query(app_models.Comment)
                .filter_by(question_id=parent.id, author_id=author.id)
                .first()
            )
        else:
            parent = articles[c["article"]]
            comment = (
                db.query(app_models.Comment)
                .filter_by(article_id=parent.id, author_id=author.id)
                .first()
            )
        _require(comment is not None, f"comment {c['key']} is gone")
        _require(c["body"] in str(comment.body), f"comment {c['key']} body changed")


def verify(db, *, deep: bool = False) -> None:
    """Assert the dataset is intact. Raises AssertionError with the detail.

    Checks content, not just row counts: a migration that drops a column or
    mangles a value leaves the count untouched. Relationships are dereferenced
    for the same reason -- a broken foreign key survives a count.
    """
    users = _verify_users(db)
    site = _verify_site(db, users)
    columns = _verify_columns(db, users)
    questions = _verify_questions(db, users, site)
    answers = _verify_answers(db, users, questions)
    articles = _verify_articles(db, columns)

    _verify_follows(users)
    _verify_upvotes(db, users, questions, answers, articles)
    _verify_comments(db, users, questions, articles)

    if not deep:
        return

    a = users["account_a"]
    b = users["account_b"]
    question = questions[DEEP_QUESTION_KEY]

    deep_answer = (
        db.query(app_models.Answer)
        .filter_by(question_id=question.id, author_id=b.id)
        .first()
    )
    _require(deep_answer is not None, "deep-flow answer is gone")
    _require(
        DEEP_ANSWER_BODY in str(deep_answer.body),
        f"deep-flow answer body changed: {deep_answer.body!r}",
    )

    _require(a in b.followed, "the deep-flow follow edge is gone")

    for verb in ("create_question", "answer_question"):
        activities = _activities_for_verb(db, verb)
        _require(activities, f"no Activity survived for {verb}")
        for activity in activities:
            _require(
                activity.event_json not in (None, ""),
                f"{verb} Activity lost its payload",
            )

    feeds = db.query(app_models.Feed).count()
    _require(feeds > 0, "every Feed row is gone")
    for feed in db.query(app_models.Feed).all():
        _require(feed.activity is not None, "a Feed row lost its Activity FK")

    notifications = db.query(app_models.Notification).count()
    _require(notifications > 0, "every Notification row is gone")
