"""Feed padding: when it happens, and what it is not allowed to do.

The padding exists so a user who follows nobody does not see a blank home
page. These pin the boundaries the version in #85 had and the rewrite of it
lost -- it padded any page that was not completely full, could return more
items than the caller asked for, and could repeat an activity that was already
in the feed.
"""

import datetime
from typing import List, Optional

import pytest
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.event import CreateQuestionInternal, EventInternal
from chafan_core.app.schemas.question import QuestionCreate
from chafan_core.app.schemas.site import SiteCreate
from chafan_core.app.schemas.user import UserCreate
from chafan_core.app.services import events, feed as feed_service, feed_fill
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)


@pytest.fixture
def ctx(db: Session):
    """A RequestContext sharing the suite's session.

    Same reasoning as test_events_distribute: a fresh one would open a second
    transaction and block on rows this one holds.
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


def _public_site(db: Session, moderator):
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


def _ask(ctx: RequestContext, author, site):
    """A question plus the Activity and Feed rows its creation distributes."""
    db = ctx.get_db()
    question = crud.question.create_with_author(
        db,
        obj_in=QuestionCreate(
            site_uuid=site.uuid, title=f"Q {random_short_lower_string()}"
        ),
        author_id=author.id,
    )
    db.flush()
    events.distribute(
        ctx,
        EventInternal(
            created_at=datetime.datetime.now(tz=datetime.timezone.utc),
            content=CreateQuestionInternal(
                subject_id=author.id, question_id=question.id
            ),
        ),
    )
    db.flush()
    return question


def _feed(
    ctx: RequestContext,
    user,
    *,
    limit: int = 20,
    before_activity_id: Optional[int] = None,
    random: bool = False,
    subject_user_uuid: Optional[str] = None,
) -> List[schemas.Activity]:
    return feed_service.get_user_activity(
        ctx,
        current_user_id=user.id,
        before_activity_id=before_activity_id,
        limit=limit,
        random=random,
        subject_user_uuid=subject_user_uuid,
    )


def test_empty_feed_is_padded(ctx: RequestContext) -> None:
    """The point of the feature: follow nobody, still see a page."""
    db = ctx.get_db()
    author = _user(db)
    site = _public_site(db, moderator=author)
    _ask(ctx, author, site)

    # The newcomer follows nobody, so they have no Feed rows at all.
    newcomer = _user(db)
    db.flush()
    assert db.query(models.Feed).filter_by(receiver_id=newcomer.id).count() == 0

    activities = _feed(ctx, newcomer)

    assert activities, "a user with no audience must still get a page"


def test_padding_never_exceeds_the_requested_limit(ctx: RequestContext) -> None:
    """The old caller asked for a full `limit` of padding on top of the feed."""
    db = ctx.get_db()
    author = _user(db)
    site = _public_site(db, moderator=author)
    for _ in range(3):
        _ask(ctx, author, site)
    newcomer = _user(db)
    db.flush()

    activities = _feed(ctx, newcomer, limit=2)

    assert len(activities) <= 2


def test_padding_does_not_repeat_the_feed(ctx: RequestContext) -> None:
    """The old caller extended without checking for overlap."""
    db = ctx.get_db()
    author = _user(db)
    follower = _user(db)
    author.followers.append(follower)
    site = _public_site(db, moderator=author)
    _ask(ctx, author, site)
    db.flush()

    activities = _feed(ctx, follower)

    ids = [a.id for a in activities]
    assert len(ids) == len(set(ids)), "an activity must not appear twice"


def test_a_full_feed_is_not_padded(ctx: RequestContext) -> None:
    """Padding is for an empty page, not for one item short of a full one."""
    db = ctx.get_db()
    author = _user(db)
    follower = _user(db)
    author.followers.append(follower)
    site = _public_site(db, moderator=author)
    for _ in range(feed_fill.FILL_BELOW):
        _ask(ctx, author, site)
    db.flush()

    activities = _feed(ctx, follower, limit=20)

    assert len(activities) == feed_fill.FILL_BELOW, (
        "a feed at or above the threshold is returned as-is, "
        "even though the page is not full"
    )


def test_later_pages_are_not_padded(ctx: RequestContext) -> None:
    """A blank second page means the end of the feed, not a page to fill."""
    db = ctx.get_db()
    author = _user(db)
    site = _public_site(db, moderator=author)
    _ask(ctx, author, site)
    newcomer = _user(db)
    db.flush()

    activities = _feed(ctx, newcomer, before_activity_id=1)

    assert activities == []


def test_subject_timelines_are_never_padded(ctx: RequestContext) -> None:
    """A profile must not claim its subject did something they did not."""
    db = ctx.get_db()
    author = _user(db)
    site = _public_site(db, moderator=author)
    _ask(ctx, author, site)
    silent = _user(db)
    db.flush()

    activities = _feed(ctx, author, subject_user_uuid=silent.uuid)

    assert activities == [], "a silent user's profile stays empty"
