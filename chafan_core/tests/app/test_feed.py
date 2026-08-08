"""GET /activities/: the two timelines behind it, and the padding on one.

The endpoint answers two different questions. The home feed asks what was
delivered to the viewer; a profile asks what one user did. Half of these tests
pin that split, the other half pin the padding that keeps a new user's home
page from rendering blank.
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


def _private_site(db: Session, moderator):
    return crud.site.create_with_permission_type(
        db,
        obj_in=SiteCreate(
            name=f"S {random_short_lower_string()}",
            subdomain=random_short_lower_string(),
            description="d",
            permission_type="private",
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


# ---------------------------------------------------------------------------
# The subject timeline (step 4). Reads the event log, not the delivery table.
# ---------------------------------------------------------------------------


def test_profile_is_complete_without_an_audience(ctx: RequestContext) -> None:
    """The bug this whole plan exists to fix.

    No followers and no column subscribers means no Feed rows, so the old
    subject query -- which read Feed -- returned nothing however much the user
    had posted.
    """
    db = ctx.get_db()
    loner = _user(db)
    site = _public_site(db, moderator=loner)
    _ask(ctx, loner, site)
    _ask(ctx, loner, site)
    db.flush()

    # The precondition that made the old query fail: no audience, so the
    # fan-out wrote nothing, so reading Feed found nothing to return.
    assert loner.followers.count() == 0
    mine = [a.id for a in db.query(models.Activity).filter_by(subject_user_id=loner.id)]
    assert len(mine) == 2
    assert (
        db.query(models.Feed).filter(models.Feed.activity_id.in_(mine)).count() == 0
    ), "no audience means no delivery rows"

    viewer = _user(db)
    db.flush()
    activities = _feed(ctx, viewer, subject_user_uuid=loner.uuid)

    assert len(activities) == 2


def test_own_profile_needs_no_superuser_trick(ctx: RequestContext) -> None:
    """You do not follow yourself, which is what the deleted v1 worked around."""
    db = ctx.get_db()
    author = _user(db)
    site = _public_site(db, moderator=author)
    _ask(ctx, author, site)
    db.flush()

    activities = _feed(ctx, author, subject_user_uuid=author.uuid)

    assert len(activities) == 1


def test_subject_timeline_has_no_duplicates(ctx: RequestContext) -> None:
    """One activity, once -- however many people it was delivered to.

    Reading Feed across all receivers returned it once per follower, which is
    what the `limit * 2` over-fetch and the seen-set existed to undo.
    """
    db = ctx.get_db()
    author = _user(db)
    for _ in range(3):
        author.followers.append(_user(db))
    site = _public_site(db, moderator=author)
    _ask(ctx, author, site)
    db.flush()
    viewer = _user(db)
    db.flush()

    activities = _feed(ctx, viewer, subject_user_uuid=author.uuid)

    ids = [a.id for a in activities]
    assert ids == sorted(set(ids), reverse=True)
    assert len(ids) == 1, "three followers, one activity"


def test_private_site_activity_stays_hidden(ctx: RequestContext) -> None:
    """The safety property: reachable by the query is not the same as visible.

    The Activity row is now returned by the subject query regardless of
    delivery, so the per-viewer responder gate is the only thing standing
    between an outsider and a private site's contents.
    """
    db = ctx.get_db()
    author = _user(db)
    public = _public_site(db, moderator=author)
    private = _private_site(db, moderator=author)
    _ask(ctx, author, public)
    _ask(ctx, author, private)
    db.flush()
    outsider = _user(db)
    db.flush()

    seen = _feed(ctx, outsider, subject_user_uuid=author.uuid)

    subdomains = {a.site.subdomain for a in seen if a.site}
    assert public.subdomain in subdomains
    assert private.subdomain not in subdomains, "a non-member must not see it"
    assert len(seen) == 1, "the private item is dropped, not merely unlabelled"


def test_unknown_subject_uuid_is_empty_not_an_error(ctx: RequestContext) -> None:
    """A reader asking about somebody who is gone, not a malformed request."""
    db = ctx.get_db()
    viewer = _user(db)
    db.flush()

    assert _feed(ctx, viewer, subject_user_uuid="no-such-user-uuid") == []


def test_activity_without_a_subject_is_absent(ctx: RequestContext) -> None:
    """Null-subject rows never appear in a subject query -- containment."""
    db = ctx.get_db()
    author = _user(db)
    site = _public_site(db, moderator=author)
    _ask(ctx, author, site)
    db.flush()
    db.query(models.Activity).filter_by(subject_user_id=author.id).update(
        {"subject_user_id": None}
    )
    db.flush()
    viewer = _user(db)
    db.flush()

    assert _feed(ctx, viewer, subject_user_uuid=author.uuid) == []


def test_subject_timeline_paginates(ctx: RequestContext) -> None:
    db = ctx.get_db()
    author = _user(db)
    site = _public_site(db, moderator=author)
    for _ in range(3):
        _ask(ctx, author, site)
    db.flush()
    viewer = _user(db)
    db.flush()

    first = _feed(ctx, viewer, subject_user_uuid=author.uuid, limit=2)
    assert len(first) == 2

    rest = _feed(
        ctx,
        viewer,
        subject_user_uuid=author.uuid,
        limit=2,
        before_activity_id=first[-1].id,
    )
    assert len(rest) == 1
    assert rest[0].id < first[-1].id
