"""The step-3 backfill, against rows events.distribute actually wrote.

The strong assertion is round-trip: null the column on real rows, run the
backfill, and get back exactly what `distribute` put there. That makes the test
self-checking rather than a restatement of the extraction, and it stays honest
as verbs are added -- nothing here names a verb.
"""

import datetime
import importlib.util
import pathlib

import pytest
from sqlalchemy import func
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.event import CreateQuestionInternal, EventInternal
from chafan_core.app.schemas.question import QuestionCreate
from chafan_core.app.schemas.site import SiteCreate
from chafan_core.app.schemas.user import UserCreate
from chafan_core.app.services import events
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)

_SCRIPT = (
    pathlib.Path(__file__).resolve().parents[3]
    / "scripts"
    / "backfill_activity_subject.py"
)


def _load_script():
    """Import the script by path -- scripts/ is not a package."""
    spec = importlib.util.spec_from_file_location("backfill_activity_subject", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backfill_script = _load_script()


@pytest.fixture
def ctx(db: Session):
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


def _activity(ctx: RequestContext, author):
    """One Activity, written the way the application writes them."""
    db = ctx.get_db()
    site = crud.site.create_with_permission_type(
        db,
        obj_in=SiteCreate(
            name=f"S {random_short_lower_string()}",
            subdomain=random_short_lower_string(),
            description="d",
            permission_type="public",
        ),
        moderator=author,
        category_topic_id=None,
    )
    question = crud.question.create_with_author(
        db,
        obj_in=QuestionCreate(
            site_uuid=site.uuid, title=f"Q {random_short_lower_string()}"
        ),
        author_id=author.id,
    )
    db.flush()
    activity = events.distribute(
        ctx,
        EventInternal(
            created_at=datetime.datetime.now(tz=datetime.timezone.utc),
            content=CreateQuestionInternal(
                subject_id=author.id, question_id=question.id
            ),
        ),
    )
    db.flush()
    assert activity is not None
    return activity


def test_round_trips_what_distribute_wrote(ctx: RequestContext) -> None:
    """Null the column on real rows; the backfill must restore it exactly."""
    db = ctx.get_db()
    author = _user(db)
    written = {
        a.id: a.subject_user_id for a in (_activity(ctx, author) for _ in range(3))
    }
    assert all(
        v is not None for v in written.values()
    ), "step 2 should have filled these"

    for activity_id in written:
        db.query(models.Activity).filter_by(id=activity_id).update(
            {"subject_user_id": None}
        )
    db.flush()

    backfill_script.backfill(db, batch_size=2)

    restored = {
        a.id: a.subject_user_id
        for a in db.query(models.Activity).filter(models.Activity.id.in_(list(written)))
    }
    assert restored == written


def test_dry_run_writes_nothing(ctx: RequestContext) -> None:
    db = ctx.get_db()
    author = _user(db)
    activity = _activity(ctx, author)
    activity_id = activity.id
    db.query(models.Activity).filter_by(id=activity_id).update(
        {"subject_user_id": None}
    )
    db.flush()

    stats = backfill_script.backfill(db, dry_run=True)

    assert stats["filled"] >= 1, "a dry run still reports what it would do"
    assert (
        db.query(models.Activity).filter_by(id=activity_id).one().subject_user_id
        is None
    ), "a dry run must leave the column untouched"


def test_rerunning_fills_nothing_further(ctx: RequestContext) -> None:
    """Idempotent: a second pass has nothing left to fill.

    Note `filled`, not `scanned`. Rows that can never be filled -- unreadable
    payload, vanished subject -- stay null by design, so every later run
    re-examines them. That is the cost of not marking them, and at production
    scale it is nothing.
    """
    db = ctx.get_db()
    author = _user(db)
    activity = _activity(ctx, author)
    db.query(models.Activity).filter_by(id=activity.id).update(
        {"subject_user_id": None}
    )
    db.flush()

    first = backfill_script.backfill(db)
    second = backfill_script.backfill(db)

    assert first["filled"] >= 1
    assert second["filled"] == 0, "nothing fillable is left after the first pass"


def test_unreadable_payload_is_skipped_not_fatal(ctx: RequestContext) -> None:
    """One retired code path's row must not stop the rest of the table."""
    db = ctx.get_db()
    author = _user(db)
    broken = _activity(ctx, author)
    intact = _activity(ctx, author)
    intact_subject = intact.subject_user_id
    db.query(models.Activity).filter_by(id=broken.id).update(
        {"subject_user_id": None, "event_json": "this is not json"}
    )
    db.query(models.Activity).filter_by(id=intact.id).update({"subject_user_id": None})
    db.flush()

    stats = backfill_script.backfill(db)

    assert stats["skipped_unreadable"] >= 1
    assert (
        db.query(models.Activity).filter_by(id=broken.id).one().subject_user_id is None
    ), "an unreadable row stays null"
    assert (
        db.query(models.Activity).filter_by(id=intact.id).one().subject_user_id
        == intact_subject
    ), "the readable row beside it is still filled"


def test_vanished_subject_is_skipped_not_fatal(ctx: RequestContext) -> None:
    """The other reason the column is nullable."""
    db = ctx.get_db()
    author = _user(db)
    activity = _activity(ctx, author)
    missing_id = db.query(func.max(models.User.id)).scalar() + 1
    payload = activity.event_json.replace(
        f'"subject_id":{author.id}', f'"subject_id":{missing_id}'
    )
    assert payload != activity.event_json, "the payload shape changed; fix this test"
    db.query(models.Activity).filter_by(id=activity.id).update(
        {"subject_user_id": None, "event_json": payload}
    )
    db.flush()

    stats = backfill_script.backfill(db)

    assert stats["skipped_missing_user"] >= 1
    assert (
        db.query(models.Activity).filter_by(id=activity.id).one().subject_user_id
        is None
    )


@pytest.mark.parametrize(
    "payload,expected",
    [
        ('{"created_at":"x","content":{"verb":"v","subject_id":7}}', 7),
        ('{"content":{"verb":"v"}}', None),
        ('{"content":{"verb":"v","subject_id":"7"}}', None),
        ('{"content":null}', None),
        ('{"no_content":1}', None),
        ("not json at all", None),
        ("", None),
        (None, None),
    ],
)
def test_subject_id_extraction(payload, expected) -> None:
    assert backfill_script.subject_id_of(payload) == expected
