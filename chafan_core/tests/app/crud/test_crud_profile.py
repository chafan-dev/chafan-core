import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.profile import ProfileCreate, ProfileUpdate
from chafan_core.app.schemas.site import SiteCreate
from chafan_core.app.schemas.user import UserCreate
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


def test_create_profile_with_owner(db: Session) -> None:
    """Test creating a profile with owner."""
    user = _create_test_user(db)
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator)

    profile_in = ProfileCreate(
        site_uuid=site.uuid,
        owner_uuid=user.uuid,
    )

    profile = crud.profile.create_with_owner(db, obj_in=profile_in)

    assert profile is not None
    assert profile.owner_id == user.id
    assert profile.site_id == site.id
    assert profile.karma == 0  # Default karma


def test_get_profile_by_user_and_site(db: Session) -> None:
    """Test retrieving a profile by user and site."""
    user = _create_test_user(db)
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator)

    profile_in = ProfileCreate(
        site_uuid=site.uuid,
        owner_uuid=user.uuid,
    )

    profile = crud.profile.create_with_owner(db, obj_in=profile_in)

    retrieved_profile = crud.profile.get_by_user_and_site(
        db, owner_id=user.id, site_id=site.id
    )
    assert retrieved_profile is not None
    assert retrieved_profile.id == profile.id
    assert retrieved_profile.owner_id == user.id
    assert retrieved_profile.site_id == site.id


def test_get_profile_by_user_and_site_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get_by_user_and_site returns None when profile doesn't exist."""
    user = _create_test_user(db)
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator)

    # Don't create a profile, just try to get it
    retrieved_profile = crud.profile.get_by_user_and_site(
        db, owner_id=user.id, site_id=site.id
    )
    assert retrieved_profile is None


def test_remove_profile_by_user_and_site(db: Session) -> None:
    """Test removing a profile by user and site."""
    user = _create_test_user(db)
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator)

    profile_in = ProfileCreate(
        site_uuid=site.uuid,
        owner_uuid=user.uuid,
    )

    profile = crud.profile.create_with_owner(db, obj_in=profile_in)
    profile_id = profile.id

    # Remove the profile
    removed_profile = crud.profile.remove_by_user_and_site(
        db, owner_id=user.id, site_id=site.id
    )
    assert removed_profile is not None
    assert removed_profile.id == profile_id

    # Verify it's removed
    retrieved_profile = crud.profile.get_by_user_and_site(
        db, owner_id=user.id, site_id=site.id
    )
    assert retrieved_profile is None


def test_remove_profile_returns_none_for_nonexistent(db: Session) -> None:
    """Test that remove_by_user_and_site returns None when profile doesn't exist."""
    user = _create_test_user(db)
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator)

    # Don't create a profile, just try to remove it
    result = crud.profile.remove_by_user_and_site(
        db, owner_id=user.id, site_id=site.id
    )
    assert result is None


def test_user_can_have_multiple_profiles_in_different_sites(db: Session) -> None:
    """Test that a user can have profiles in multiple sites."""
    user = _create_test_user(db)
    moderator = _create_test_user(db)
    site1 = _create_test_site(db, moderator)
    site2 = _create_test_site(db, moderator)

    profile1_in = ProfileCreate(
        site_uuid=site1.uuid,
        owner_uuid=user.uuid,
    )
    profile1 = crud.profile.create_with_owner(db, obj_in=profile1_in)

    profile2_in = ProfileCreate(
        site_uuid=site2.uuid,
        owner_uuid=user.uuid,
    )
    profile2 = crud.profile.create_with_owner(db, obj_in=profile2_in)

    # Both profiles should exist
    retrieved_profile1 = crud.profile.get_by_user_and_site(
        db, owner_id=user.id, site_id=site1.id
    )
    retrieved_profile2 = crud.profile.get_by_user_and_site(
        db, owner_id=user.id, site_id=site2.id
    )

    assert retrieved_profile1 is not None
    assert retrieved_profile2 is not None
    assert retrieved_profile1.id == profile1.id
    assert retrieved_profile2.id == profile2.id
    assert retrieved_profile1.id != retrieved_profile2.id


def test_multiple_users_can_have_profiles_in_same_site(db: Session) -> None:
    """Test that multiple users can have profiles in the same site."""
    user1 = _create_test_user(db)
    user2 = _create_test_user(db)
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator)

    profile1_in = ProfileCreate(
        site_uuid=site.uuid,
        owner_uuid=user1.uuid,
    )
    profile1 = crud.profile.create_with_owner(db, obj_in=profile1_in)

    profile2_in = ProfileCreate(
        site_uuid=site.uuid,
        owner_uuid=user2.uuid,
    )
    profile2 = crud.profile.create_with_owner(db, obj_in=profile2_in)

    # Both profiles should exist
    retrieved_profile1 = crud.profile.get_by_user_and_site(
        db, owner_id=user1.id, site_id=site.id
    )
    retrieved_profile2 = crud.profile.get_by_user_and_site(
        db, owner_id=user2.id, site_id=site.id
    )

    assert retrieved_profile1 is not None
    assert retrieved_profile2 is not None
    assert retrieved_profile1.id == profile1.id
    assert retrieved_profile2.id == profile2.id


def test_update_profile(db: Session) -> None:
    """Test updating a profile."""
    user = _create_test_user(db)
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator)

    profile_in = ProfileCreate(
        site_uuid=site.uuid,
        owner_uuid=user.uuid,
    )

    profile = crud.profile.create_with_owner(db, obj_in=profile_in)

    # Update karma
    crud.profile.update(db, db_obj=profile, obj_in={"karma": 100})

    db.refresh(profile)
    assert profile.karma == 100


def test_get_profile(db: Session) -> None:
    """Test getting a profile by ID."""
    user = _create_test_user(db)
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator)

    profile_in = ProfileCreate(
        site_uuid=site.uuid,
        owner_uuid=user.uuid,
    )

    profile = crud.profile.create_with_owner(db, obj_in=profile_in)

    retrieved_profile = crud.profile.get(db, id=profile.id)
    assert retrieved_profile is not None
    assert retrieved_profile.id == profile.id


def test_remove_only_removes_specific_profile(db: Session) -> None:
    """Test that removing a profile only removes the specific one."""
    user = _create_test_user(db)
    moderator = _create_test_user(db)
    site1 = _create_test_site(db, moderator)
    site2 = _create_test_site(db, moderator)

    profile1_in = ProfileCreate(
        site_uuid=site1.uuid,
        owner_uuid=user.uuid,
    )
    crud.profile.create_with_owner(db, obj_in=profile1_in)

    profile2_in = ProfileCreate(
        site_uuid=site2.uuid,
        owner_uuid=user.uuid,
    )
    profile2 = crud.profile.create_with_owner(db, obj_in=profile2_in)

    # Remove profile from site1
    crud.profile.remove_by_user_and_site(db, owner_id=user.id, site_id=site1.id)

    # Profile in site1 should be gone
    assert crud.profile.get_by_user_and_site(db, owner_id=user.id, site_id=site1.id) is None

    # Profile in site2 should still exist
    profile2_retrieved = crud.profile.get_by_user_and_site(
        db, owner_id=user.id, site_id=site2.id
    )
    assert profile2_retrieved is not None
    assert profile2_retrieved.id == profile2.id
