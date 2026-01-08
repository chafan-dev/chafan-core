import asyncio
import datetime
from sqlalchemy.orm import Session

from chafan_core.app import crud
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


def test_create_invitation_link(db: Session) -> None:
    """Test creating an invitation link."""
    inviter = _create_test_user(db)
    site = _create_test_site(db, moderator=inviter)

    invitation_link = asyncio.run(
        crud.invitation_link.create_invitation(
            db, invited_to_site_id=site.id, inviter=inviter
        )
    )

    assert invitation_link is not None
    assert invitation_link.inviter_id == inviter.id
    assert invitation_link.invited_to_site_id == site.id
    assert invitation_link.uuid is not None
    assert invitation_link.created_at is not None
    assert invitation_link.expired_at is not None
    assert invitation_link.remaining_quota == 100


def test_create_invitation_link_without_site(db: Session) -> None:
    """Test creating an invitation link without a specific site."""
    inviter = _create_test_user(db)

    invitation_link = asyncio.run(
        crud.invitation_link.create_invitation(
            db, invited_to_site_id=None, inviter=inviter
        )
    )

    assert invitation_link is not None
    assert invitation_link.inviter_id == inviter.id
    assert invitation_link.invited_to_site_id is None


def test_invitation_link_expiration(db: Session) -> None:
    """Test that invitation link has correct expiration time (7 days)."""
    inviter = _create_test_user(db)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    invitation_link = asyncio.run(
        crud.invitation_link.create_invitation(
            db, invited_to_site_id=None, inviter=inviter
        )
    )

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    # Expiration should be about 7 days from now
    expected_min_expiry = before_create + datetime.timedelta(days=7)
    expected_max_expiry = after_create + datetime.timedelta(days=7)

    assert expected_min_expiry <= invitation_link.expired_at <= expected_max_expiry


def test_get_invitation_link_by_id(db: Session) -> None:
    """Test getting an invitation link by ID."""
    inviter = _create_test_user(db)

    invitation_link = asyncio.run(
        crud.invitation_link.create_invitation(
            db, invited_to_site_id=None, inviter=inviter
        )
    )

    retrieved = crud.invitation_link.get(db, id=invitation_link.id)
    assert retrieved is not None
    assert retrieved.id == invitation_link.id


def test_get_invitation_link_by_uuid(db: Session) -> None:
    """Test getting an invitation link by UUID."""
    inviter = _create_test_user(db)

    invitation_link = asyncio.run(
        crud.invitation_link.create_invitation(
            db, invited_to_site_id=None, inviter=inviter
        )
    )

    retrieved = crud.invitation_link.get_by_uuid(db, uuid=invitation_link.uuid)
    assert retrieved is not None
    assert retrieved.uuid == invitation_link.uuid


def test_get_invitation_link_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent invitation link."""
    result = crud.invitation_link.get(db, id=99999999)
    assert result is None


def test_get_invitation_link_by_uuid_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get_by_uuid returns None for non-existent UUID."""
    result = crud.invitation_link.get_by_uuid(db, uuid="nonexistent-uuid")
    assert result is None


def test_invitation_link_timestamps(db: Session) -> None:
    """Test that invitation links have correct timestamps."""
    inviter = _create_test_user(db)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    invitation_link = asyncio.run(
        crud.invitation_link.create_invitation(
            db, invited_to_site_id=None, inviter=inviter
        )
    )

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert invitation_link.created_at is not None
    assert before_create <= invitation_link.created_at <= after_create


def test_multiple_invitation_links_from_same_inviter(db: Session) -> None:
    """Test that an inviter can create multiple invitation links."""
    inviter = _create_test_user(db)

    links = []
    for _ in range(3):
        link = asyncio.run(
            crud.invitation_link.create_invitation(
                db, invited_to_site_id=None, inviter=inviter
            )
        )
        links.append(link)

    assert len(links) == 3
    # Each link should have unique UUID
    uuids = [link.uuid for link in links]
    assert len(set(uuids)) == 3


def test_invitation_links_for_different_sites(db: Session) -> None:
    """Test creating invitation links for different sites."""
    inviter = _create_test_user(db)
    site1 = _create_test_site(db, moderator=inviter)
    site2 = _create_test_site(db, moderator=inviter)

    link1 = asyncio.run(
        crud.invitation_link.create_invitation(
            db, invited_to_site_id=site1.id, inviter=inviter
        )
    )

    link2 = asyncio.run(
        crud.invitation_link.create_invitation(
            db, invited_to_site_id=site2.id, inviter=inviter
        )
    )

    assert link1.invited_to_site_id == site1.id
    assert link2.invited_to_site_id == site2.id
    assert link1.uuid != link2.uuid
