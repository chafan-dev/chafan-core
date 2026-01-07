import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.user import UserCreate, UserInvite
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


def test_create_invitation(db: Session) -> None:
    """Test creating an invitation."""
    inviter = _create_test_user(db)
    invited_user = _create_test_user(db)
    site = _create_test_site(db, moderator=inviter)

    user_invite = UserInvite(
        user_uuid=invited_user.uuid,
        site_uuid=site.uuid,
    )

    invitation = crud.invitation.create_invitation(
        db, user_invite=user_invite, is_sent=True, inviter=inviter
    )

    assert invitation is not None
    assert invitation.inviter_id == inviter.id
    assert invitation.invited_user_id == invited_user.id
    assert invitation.invited_to_site_id == site.id
    assert invitation.is_sent is True
    assert invitation.created_at is not None


def test_create_invitation_not_sent(db: Session) -> None:
    """Test creating an invitation that is not yet sent."""
    inviter = _create_test_user(db)
    invited_user = _create_test_user(db)
    site = _create_test_site(db, moderator=inviter)

    user_invite = UserInvite(
        user_uuid=invited_user.uuid,
        site_uuid=site.uuid,
    )

    invitation = crud.invitation.create_invitation(
        db, user_invite=user_invite, is_sent=False, inviter=inviter
    )

    assert invitation is not None
    assert invitation.is_sent is False


def test_create_invitation_returns_none_for_invalid_user(db: Session) -> None:
    """Test that create_invitation returns None for invalid user UUID."""
    inviter = _create_test_user(db)
    site = _create_test_site(db, moderator=inviter)

    user_invite = UserInvite(
        user_uuid="nonexistent-uuid",
        site_uuid=site.uuid,
    )

    invitation = crud.invitation.create_invitation(
        db, user_invite=user_invite, is_sent=True, inviter=inviter
    )

    assert invitation is None


def test_create_invitation_returns_none_for_invalid_site(db: Session) -> None:
    """Test that create_invitation returns None for invalid site UUID."""
    inviter = _create_test_user(db)
    invited_user = _create_test_user(db)

    user_invite = UserInvite(
        user_uuid=invited_user.uuid,
        site_uuid="nonexistent-site-uuid",
    )

    invitation = crud.invitation.create_invitation(
        db, user_invite=user_invite, is_sent=True, inviter=inviter
    )

    assert invitation is None


def test_get_invitation_by_id(db: Session) -> None:
    """Test getting an invitation by ID."""
    inviter = _create_test_user(db)
    invited_user = _create_test_user(db)
    site = _create_test_site(db, moderator=inviter)

    user_invite = UserInvite(
        user_uuid=invited_user.uuid,
        site_uuid=site.uuid,
    )

    invitation = crud.invitation.create_invitation(
        db, user_invite=user_invite, is_sent=True, inviter=inviter
    )

    retrieved = crud.invitation.get(db, id=invitation.id)
    assert retrieved is not None
    assert retrieved.id == invitation.id


def test_get_invitation_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent invitation."""
    result = crud.invitation.get(db, id=99999999)
    assert result is None


def test_get_by_email_returns_none_when_not_found(db: Session) -> None:
    """Test that get_by_email returns None when not found."""
    result = crud.invitation.get_by_email(db, email="nonexistent@example.com")
    assert result is None


def test_invitation_timestamps(db: Session) -> None:
    """Test that invitations have correct timestamps."""
    import datetime

    inviter = _create_test_user(db)
    invited_user = _create_test_user(db)
    site = _create_test_site(db, moderator=inviter)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    user_invite = UserInvite(
        user_uuid=invited_user.uuid,
        site_uuid=site.uuid,
    )

    invitation = crud.invitation.create_invitation(
        db, user_invite=user_invite, is_sent=True, inviter=inviter
    )

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert invitation.created_at is not None
    assert before_create <= invitation.created_at <= after_create


def test_multiple_invitations_from_same_inviter(db: Session) -> None:
    """Test that an inviter can send multiple invitations."""
    inviter = _create_test_user(db)
    site = _create_test_site(db, moderator=inviter)

    invitations = []
    for _ in range(3):
        invited_user = _create_test_user(db)
        user_invite = UserInvite(
            user_uuid=invited_user.uuid,
            site_uuid=site.uuid,
        )
        invitation = crud.invitation.create_invitation(
            db, user_invite=user_invite, is_sent=True, inviter=inviter
        )
        invitations.append(invitation)

    assert len(invitations) == 3
    assert all(inv.inviter_id == inviter.id for inv in invitations)


def test_invitations_to_different_sites(db: Session) -> None:
    """Test inviting a user to different sites."""
    inviter = _create_test_user(db)
    invited_user = _create_test_user(db)

    site1 = _create_test_site(db, moderator=inviter)
    site2 = _create_test_site(db, moderator=inviter)

    for site in [site1, site2]:
        user_invite = UserInvite(
            user_uuid=invited_user.uuid,
            site_uuid=site.uuid,
        )
        invitation = crud.invitation.create_invitation(
            db, user_invite=user_invite, is_sent=True, inviter=inviter
        )
        assert invitation is not None
        assert invitation.invited_to_site_id == site.id
