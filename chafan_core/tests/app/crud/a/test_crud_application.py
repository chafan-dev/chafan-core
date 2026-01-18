import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.application import ApplicationCreate, ApplicationUpdate
from chafan_core.app.schemas.user import UserCreate
from chafan_core.app.schemas.site import SiteCreate
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)


def _create_test_user(db: Session):
    """Helper to create a test user."""
    user_in = UserCreate(
        email=random_email(),
        password=random_password(),
        handle=random_short_lower_string(),
    )
    return asyncio.run(crud.user.create(db, obj_in=user_in))


def _create_test_site(db: Session, moderator):
    """Helper to create a test site."""
    site_in = SiteCreate(
        name=f"Test Site {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Test site",
        permission_type="private",
    )
    return crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )


def test_create_application_with_applicant(db: Session) -> None:
    """Test creating an application with an applicant."""
    moderator = _create_test_user(db)
    applicant = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    application_in = ApplicationCreate(applied_site_id=site.id)

    application = crud.application.create_with_applicant(
        db, create_in=application_in, applicant_id=applicant.id
    )

    assert application is not None
    assert application.applicant_id == applicant.id
    assert application.applied_site_id == site.id
    assert application.pending is True
    assert application.created_at is not None


def test_get_pending_applications(db: Session) -> None:
    """Test getting pending applications for a site."""
    moderator = _create_test_user(db)
    applicant1 = _create_test_user(db)
    applicant2 = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    # Create pending applications
    for applicant in [applicant1, applicant2]:
        application_in = ApplicationCreate(applied_site_id=site.id)
        crud.application.create_with_applicant(
            db, create_in=application_in, applicant_id=applicant.id
        )

    pending = crud.application.get_pending_applications(db, site_id=site.id)
    assert len(pending) >= 2

    # All should be pending
    for app in pending:
        assert app.pending is True


def test_get_pending_applications_excludes_non_pending(db: Session) -> None:
    """Test that get_pending_applications excludes non-pending applications."""
    moderator = _create_test_user(db)
    applicant = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    # Create and approve an application
    application_in = ApplicationCreate(applied_site_id=site.id)
    application = crud.application.create_with_applicant(
        db, create_in=application_in, applicant_id=applicant.id
    )

    # Update to not pending
    crud.application.update(db, db_obj=application, obj_in={"pending": False})

    pending = crud.application.get_pending_applications(db, site_id=site.id)
    pending_ids = [p.id for p in pending]
    assert application.id not in pending_ids


def test_get_by_applicant_and_site(db: Session) -> None:
    """Test getting an application by applicant and site."""
    moderator = _create_test_user(db)
    applicant = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    application_in = ApplicationCreate(applied_site_id=site.id)
    created_application = crud.application.create_with_applicant(
        db, create_in=application_in, applicant_id=applicant.id
    )

    retrieved = crud.application.get_by_applicant_and_site(
        db, applicant=applicant, site=site
    )

    assert retrieved is not None
    assert retrieved.id == created_application.id


def test_get_by_applicant_and_site_returns_none_when_not_found(db: Session) -> None:
    """Test that get_by_applicant_and_site returns None when not found."""
    moderator = _create_test_user(db)
    applicant = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    # Don't create any application
    result = crud.application.get_by_applicant_and_site(
        db, applicant=applicant, site=site
    )

    assert result is None


def test_get_application_by_id(db: Session) -> None:
    """Test getting an application by ID."""
    moderator = _create_test_user(db)
    applicant = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    application_in = ApplicationCreate(applied_site_id=site.id)
    application = crud.application.create_with_applicant(
        db, create_in=application_in, applicant_id=applicant.id
    )

    retrieved = crud.application.get(db, id=application.id)
    assert retrieved is not None
    assert retrieved.id == application.id


def test_get_application_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent application."""
    result = crud.application.get(db, id=99999999)
    assert result is None


def test_update_application_pending_status(db: Session) -> None:
    """Test updating application pending status."""
    moderator = _create_test_user(db)
    applicant = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    application_in = ApplicationCreate(applied_site_id=site.id)
    application = crud.application.create_with_applicant(
        db, create_in=application_in, applicant_id=applicant.id
    )

    assert application.pending is True

    # Approve the application
    updated = crud.application.update(
        db, db_obj=application, obj_in=ApplicationUpdate(pending=False)
    )

    assert updated.pending is False


def test_application_timestamps(db: Session) -> None:
    """Test that applications have correct timestamps."""
    import datetime

    moderator = _create_test_user(db)
    applicant = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    application_in = ApplicationCreate(applied_site_id=site.id)
    application = crud.application.create_with_applicant(
        db, create_in=application_in, applicant_id=applicant.id
    )

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert application.created_at is not None
    assert before_create <= application.created_at <= after_create


def test_multiple_applications_to_same_site(db: Session) -> None:
    """Test that multiple users can apply to the same site."""
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    applicants = [_create_test_user(db) for _ in range(3)]

    for applicant in applicants:
        application_in = ApplicationCreate(applied_site_id=site.id)
        crud.application.create_with_applicant(
            db, create_in=application_in, applicant_id=applicant.id
        )

    pending = crud.application.get_pending_applications(db, site_id=site.id)
    assert len(pending) >= 3


def test_applications_to_different_sites(db: Session) -> None:
    """Test that a user can apply to different sites."""
    moderator = _create_test_user(db)
    applicant = _create_test_user(db)

    site1 = _create_test_site(db, moderator=moderator)
    site2 = _create_test_site(db, moderator=moderator)

    for site in [site1, site2]:
        application_in = ApplicationCreate(applied_site_id=site.id)
        crud.application.create_with_applicant(
            db, create_in=application_in, applicant_id=applicant.id
        )

    app1 = crud.application.get_by_applicant_and_site(
        db, applicant=applicant, site=site1
    )
    app2 = crud.application.get_by_applicant_and_site(
        db, applicant=applicant, site=site2
    )

    assert app1 is not None
    assert app2 is not None
    assert app1.id != app2.id
