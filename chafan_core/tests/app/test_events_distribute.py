"""Sink routing for events.distribute.

These pin *which* sinks each verb reaches and *who* it reaches, since that is
what the 3a refactor had to preserve while moving ~27 call sites. The audience
resolvers are exercised against real rows rather than mocked, because the whole
point of deriving from the event is that the ids resolve.
"""

import datetime
from typing import Set

import pytest
from sqlalchemy.orm import Session

from chafan_core.app.infra.request_context import RequestContext

from chafan_core.app import crud, models
from chafan_core.app.schemas.event import (
    AnswerQuestionInternal,
    CommentQuestionInternal,
    CreateQuestionInternal,
    CreateSiteNeedApprovalInternal,
    EventInternal,
    FollowUserInternal,
    UpvoteQuestionInternal,
)
from chafan_core.app.services import events
from chafan_core.app.services.activity_policy import POLICY, Audience
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)
from chafan_core.app.schemas.user import UserCreate
from chafan_core.app.schemas.site import SiteCreate
from chafan_core.app.schemas.question import QuestionCreate
from chafan_core.utils.base import get_uuid


@pytest.fixture
def ctx(db: Session):
    """A RequestContext sharing the suite's session.

    Deliberately not a fresh RequestContext: its own SessionLocal would open a
    second transaction and block on rows this one holds.
    """
    context = RequestContext()
    context.db = db
    yield context


def _user(db: Session):
    return crud.user.create(
        db,
        obj_in=UserCreate(
            email=random_email(),
            password=random_password(),
            handle=random_short_lower_string(),
        ),
    )


def _site(db: Session, moderator):
    return crud.site.create_with_permission_type(
        db,
        obj_in=SiteCreate(
            name=f"S {random_short_lower_string()}",
            subdomain=random_short_lower_string(),
            description="d",
            permission_type="public",
        ),
        moderator=moderator,
        category_topic_id=None,
    )


def _question(db: Session, author_id: int, site):
    return crud.question.create_with_author(
        db,
        obj_in=QuestionCreate(site_uuid=site.uuid, title=f"Q {random_short_lower_string()}"),
        author_id=author_id,
    )


def _now():
    return datetime.datetime.now(tz=datetime.timezone.utc)


def _activities_for(db: Session, verb: str, before_id: int):
    return [
        a
        for a in db.query(models.Activity).filter(models.Activity.id > before_id)
        if f'"verb": "{verb}"' in a.event_json or f'"verb":"{verb}"' in a.event_json
    ]


def test_create_question_writes_activity_with_site_and_fans_out(ctx) -> None:
    """The three things the old postprocess did by hand: Activity, site, Feed."""
    db = ctx.get_db()
    author = _user(db)
    follower = _user(db)
    author.followers.append(follower)
    site = _site(db, moderator=author)
    question = _question(db, author_id=author.id, site=site)
    db.flush()
    max_id = db.query(models.Activity).count() and max(
        (a.id for a in db.query(models.Activity)), default=0
    )

    activity = events.distribute(
        ctx,
        EventInternal(
            created_at=_now(),
            content=CreateQuestionInternal(
                subject_id=author.id, question_id=question.id
            ),
        ),
    )

    assert activity is not None
    assert activity.site_id == question.site_id, "site must be derived from the question"
    # SessionLocal is autoflush=False, so pending Feed rows are invisible to a
    # query until flushed.
    db.flush()
    feeds = db.query(models.Feed).filter_by(activity_id=activity.id).all()
    assert {f.receiver_id for f in feeds} == {follower.id}
    assert _activities_for(db, "create_question", max_id)


def test_no_notification_for_create_question(ctx) -> None:
    """create_question notifies nobody -- the site-members rule is v1, unapplied."""
    db = ctx.get_db()
    author = _user(db)
    site = _site(db, moderator=author)
    question = _question(db, author_id=author.id, site=site)
    db.flush()
    before = db.query(models.Notification).count()

    events.distribute(
        ctx,
        EventInternal(
            created_at=_now(),
            content=CreateQuestionInternal(
                subject_id=author.id, question_id=question.id
            ),
        ),
    )

    assert db.query(models.Notification).count() == before


def test_answer_question_notifies_question_author_but_not_self(ctx) -> None:
    """Exclusion.SUBJECT reproduces the old `question.author != answer.author` guard."""
    db = ctx.get_db()
    asker = _user(db)
    answerer = _user(db)
    site = _site(db, moderator=asker)
    question = _question(db, author_id=asker.id, site=site)
    db.flush()

    content = AnswerQuestionInternal(subject_id=answerer.id, answer_id=0)
    # Resolve the audience directly: constructing a real Answer is covered by
    # the API tests; what matters here is who the policy picks out.
    receivers = events._resolve(ctx, Audience.QUESTION_AUTHOR, content)
    assert receivers == set(), "no answer row -> nobody, rather than a crash"

    self_answer = AnswerQuestionInternal(subject_id=asker.id, answer_id=0)
    excluded = events._apply_exclusions(
        {asker.id}, POLICY["answer_question"].notify_exclusions, self_answer
    )
    assert excluded == set(), "self-answer must not notify the asker"


def test_upvote_question_writes_activity_and_notifies_nobody(ctx) -> None:
    db = ctx.get_db()
    author = _user(db)
    voter = _user(db)
    site = _site(db, moderator=author)
    question = _question(db, author_id=author.id, site=site)
    db.flush()
    before = db.query(models.Notification).count()

    activity = events.distribute(
        ctx,
        EventInternal(
            created_at=_now(),
            content=UpvoteQuestionInternal(
                subject_id=voter.id, question_id=question.id
            ),
        ),
    )

    assert activity is not None
    assert activity.site_id == question.site_id
    assert db.query(models.Notification).count() == before
    # upvote verbs are not fanned out
    assert db.query(models.Feed).filter_by(activity_id=activity.id).count() == 0


def test_sinks_narrows_destinations(ctx) -> None:
    """The escape hatch: Activity without the notification that normally rides along."""
    db = ctx.get_db()
    follower = _user(db)
    followed = _user(db)
    db.flush()
    before = db.query(models.Notification).count()

    activity = events.distribute(
        ctx,
        EventInternal(
            created_at=_now(),
            content=FollowUserInternal(subject_id=follower.id, user_id=followed.id),
        ),
        sinks=frozenset({events.Sink.ACTIVITY}),
    )

    assert activity is not None
    assert db.query(models.Notification).count() == before


def test_notification_only_sink_writes_no_activity(ctx) -> None:
    db = ctx.get_db()
    follower = _user(db)
    followed = _user(db)
    db.flush()
    before = db.query(models.Activity).count()

    activity = events.distribute(
        ctx,
        EventInternal(
            created_at=_now(),
            content=FollowUserInternal(subject_id=follower.id, user_id=followed.id),
        ),
        sinks=frozenset({events.Sink.NOTIFICATION}),
    )

    assert activity is None
    assert db.query(models.Activity).count() == before


def test_comment_activity_requires_shared_to_timeline(ctx) -> None:
    """Comments reach the timeline only when shared; distribute derives that."""
    db = ctx.get_db()
    author = _user(db)
    site = _site(db, moderator=author)
    question = _question(db, author_id=author.id, site=site)
    db.flush()

    unshared = models.Comment(
        uuid=get_uuid(),
        author_id=author.id,
        site_id=site.id,
        question_id=question.id,
        body="b",
        body_text="b",
        editor="tiptap",
        created_at=_now(),
        updated_at=_now(),
        shared_to_timeline=False,
    )
    db.add(unshared)
    db.flush()

    activity = events.distribute(
        ctx,
        EventInternal(
            created_at=_now(),
            content=CommentQuestionInternal(
                subject_id=author.id, comment_id=unshared.id, question_id=question.id
            ),
        ),
    )
    assert activity is None, "an unshared comment must not reach the timeline"

    unshared.shared_to_timeline = True
    db.flush()
    activity = events.distribute(
        ctx,
        EventInternal(
            created_at=_now(),
            content=CommentQuestionInternal(
                subject_id=author.id, comment_id=unshared.id, question_id=question.id
            ),
        ),
    )
    assert activity is not None
    assert activity.site_id == site.id


def _boom(ctx: RequestContext, content: object) -> Set[int]:
    raise RuntimeError("audience gone")


def test_unresolvable_feed_audience_does_not_lose_the_activity(
    ctx: RequestContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broken resolver costs the fan-out, not the event or the caller's writes."""
    db = ctx.get_db()
    author = _user(db)
    follower = _user(db)
    author.followers.append(follower)
    site = _site(db, moderator=author)
    question = _question(db, author_id=author.id, site=site)
    db.flush()
    # Stands in for the domain-adjacent write that precedes distribute in
    # postprocess_new_article -- the reputation award that used to be rolled
    # back when an audience blew up.
    prior_id = question.id

    monkeypatch.setitem(events._RESOLVERS, Audience.SUBJECT_FOLLOWERS, _boom)

    activity = events.distribute(
        ctx,
        EventInternal(
            created_at=_now(),
            content=CreateQuestionInternal(
                subject_id=author.id, question_id=question.id
            ),
        ),
    )

    assert activity is not None, "the event still happened; it must still be recorded"
    assert db.query(models.Feed).filter_by(activity_id=activity.id).count() == 0
    assert crud.question.get(db, id=prior_id) is not None


def test_unresolvable_notify_audience_does_not_raise(
    ctx: RequestContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = ctx.get_db()
    answerer = _user(db)
    db.flush()
    before = db.query(models.Notification).count()

    monkeypatch.setitem(events._RESOLVERS, Audience.QUESTION_AUTHOR, _boom)

    activity = events.distribute(
        ctx,
        EventInternal(
            created_at=_now(),
            content=AnswerQuestionInternal(subject_id=answerer.id, answer_id=0),
        ),
    )

    assert activity is not None
    assert db.query(models.Notification).count() == before


def test_missing_superuser_delivers_to_nobody(
    ctx: RequestContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The concrete assert this change removes: crud.user.get_superuser."""
    db = ctx.get_db()
    subject = _user(db)
    db.flush()
    before = db.query(models.Notification).count()

    monkeypatch.setattr(crud.user, "try_get_superuser", lambda db: None)

    events.distribute(
        ctx,
        EventInternal(
            created_at=_now(),
            content=CreateSiteNeedApprovalInternal(subject_id=subject.id, channel_id=1),
        ),
    )

    assert db.query(models.Notification).count() == before


def test_failed_push_still_writes_the_notification(
    ctx: RequestContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Redis blip loses the realtime ping, not the row behind it."""
    db = ctx.get_db()
    follower = _user(db)
    followed = _user(db)
    db.flush()
    before = db.query(models.Notification).count()

    def _push_boom(ctx: RequestContext, *, notif: models.Notification) -> None:
        raise RuntimeError("redis down")

    monkeypatch.setattr(events, "push_notification", _push_boom)

    events.distribute(
        ctx,
        EventInternal(
            created_at=_now(),
            content=FollowUserInternal(subject_id=follower.id, user_id=followed.id),
        ),
        sinks=frozenset({events.Sink.NOTIFICATION}),
    )

    assert db.query(models.Notification).count() == before + 1


def test_unknown_verb_is_dropped_not_raised(ctx) -> None:
    class Bogus:
        verb = "no_such_verb"
        subject_id = 1

    class BogusEvent:
        created_at = _now()
        content = Bogus()

    assert events.distribute(ctx, BogusEvent()) is None  # type: ignore[arg-type]
