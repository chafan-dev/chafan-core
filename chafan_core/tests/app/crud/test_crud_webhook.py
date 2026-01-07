import asyncio
import datetime
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.webhook import (
    WebhookCreate,
    WebhookUpdate,
    WebhookEventSpec,
    WebhookSiteEvent,
)
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


def test_create_webhook_with_site(db: Session) -> None:
    """Test creating a webhook with a site."""
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    webhook_in = WebhookCreate(
        site_uuid=site.uuid,
        event_spec=WebhookEventSpec(
            content=WebhookSiteEvent(
                new_question=True,
                new_answer=True,
                new_submission=False,
            )
        ),
        secret="test-secret-key",
        callback_url="https://example.com/webhook",
    )

    webhook = crud.webhook.create_with_site(db, obj_in=webhook_in, site_id=site.id)

    assert webhook is not None
    assert webhook.site_id == site.id
    assert webhook.secret == "test-secret-key"
    assert webhook.callback_url == "https://example.com/webhook"
    assert webhook.enabled is True
    assert webhook.updated_at is not None


def test_webhook_event_spec(db: Session) -> None:
    """Test that webhook event_spec is correctly stored."""
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    webhook_in = WebhookCreate(
        site_uuid=site.uuid,
        event_spec=WebhookEventSpec(
            content=WebhookSiteEvent(
                new_question=True,
                new_answer=False,
                new_submission=True,
            )
        ),
        secret="secret",
        callback_url="https://example.com/callback",
    )

    webhook = crud.webhook.create_with_site(db, obj_in=webhook_in, site_id=site.id)

    assert webhook.event_spec is not None


def test_get_webhook_by_id(db: Session) -> None:
    """Test getting a webhook by ID."""
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    webhook_in = WebhookCreate(
        site_uuid=site.uuid,
        event_spec=WebhookEventSpec(
            content=WebhookSiteEvent(new_question=True)
        ),
        secret="secret",
        callback_url="https://example.com/webhook",
    )

    webhook = crud.webhook.create_with_site(db, obj_in=webhook_in, site_id=site.id)

    retrieved = crud.webhook.get(db, id=webhook.id)
    assert retrieved is not None
    assert retrieved.id == webhook.id


def test_get_webhook_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent webhook."""
    result = crud.webhook.get(db, id=99999999)
    assert result is None


def test_update_webhook_enabled(db: Session) -> None:
    """Test updating webhook enabled status."""
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    webhook_in = WebhookCreate(
        site_uuid=site.uuid,
        event_spec=WebhookEventSpec(
            content=WebhookSiteEvent(new_question=True)
        ),
        secret="secret",
        callback_url="https://example.com/webhook",
    )

    webhook = crud.webhook.create_with_site(db, obj_in=webhook_in, site_id=site.id)

    assert webhook.enabled is True

    updated = crud.webhook.update(
        db, db_obj=webhook, obj_in=WebhookUpdate(enabled=False)
    )

    assert updated.enabled is False


def test_update_webhook_callback_url(db: Session) -> None:
    """Test updating webhook callback URL."""
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    webhook_in = WebhookCreate(
        site_uuid=site.uuid,
        event_spec=WebhookEventSpec(
            content=WebhookSiteEvent(new_question=True)
        ),
        secret="secret",
        callback_url="https://old.example.com/webhook",
    )

    webhook = crud.webhook.create_with_site(db, obj_in=webhook_in, site_id=site.id)

    updated = crud.webhook.update(
        db, db_obj=webhook, obj_in=WebhookUpdate(callback_url="https://new.example.com/webhook")
    )

    assert updated.callback_url == "https://new.example.com/webhook"


def test_update_webhook_secret(db: Session) -> None:
    """Test updating webhook secret."""
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    webhook_in = WebhookCreate(
        site_uuid=site.uuid,
        event_spec=WebhookEventSpec(
            content=WebhookSiteEvent(new_question=True)
        ),
        secret="old-secret",
        callback_url="https://example.com/webhook",
    )

    webhook = crud.webhook.create_with_site(db, obj_in=webhook_in, site_id=site.id)

    updated = crud.webhook.update(
        db, db_obj=webhook, obj_in=WebhookUpdate(secret="new-secret")
    )

    assert updated.secret == "new-secret"


def test_webhook_timestamps(db: Session) -> None:
    """Test that webhooks have correct timestamps."""
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    webhook_in = WebhookCreate(
        site_uuid=site.uuid,
        event_spec=WebhookEventSpec(
            content=WebhookSiteEvent(new_question=True)
        ),
        secret="secret",
        callback_url="https://example.com/webhook",
    )

    webhook = crud.webhook.create_with_site(db, obj_in=webhook_in, site_id=site.id)

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert webhook.updated_at is not None
    assert before_create <= webhook.updated_at <= after_create


def test_multiple_webhooks_for_same_site(db: Session) -> None:
    """Test creating multiple webhooks for the same site."""
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    webhooks = []
    for i in range(3):
        webhook_in = WebhookCreate(
            site_uuid=site.uuid,
            event_spec=WebhookEventSpec(
                content=WebhookSiteEvent(new_question=True)
            ),
            secret=f"secret-{i}",
            callback_url=f"https://example.com/webhook{i}",
        )
        webhook = crud.webhook.create_with_site(db, obj_in=webhook_in, site_id=site.id)
        webhooks.append(webhook)

    assert len(webhooks) == 3
    assert all(w.site_id == site.id for w in webhooks)


def test_webhooks_for_different_sites(db: Session) -> None:
    """Test creating webhooks for different sites."""
    moderator = _create_test_user(db)
    site1 = _create_test_site(db, moderator=moderator)
    site2 = _create_test_site(db, moderator=moderator)

    webhook1_in = WebhookCreate(
        site_uuid=site1.uuid,
        event_spec=WebhookEventSpec(
            content=WebhookSiteEvent(new_question=True)
        ),
        secret="secret1",
        callback_url="https://example1.com/webhook",
    )

    webhook2_in = WebhookCreate(
        site_uuid=site2.uuid,
        event_spec=WebhookEventSpec(
            content=WebhookSiteEvent(new_answer=True)
        ),
        secret="secret2",
        callback_url="https://example2.com/webhook",
    )

    webhook1 = crud.webhook.create_with_site(db, obj_in=webhook1_in, site_id=site1.id)
    webhook2 = crud.webhook.create_with_site(db, obj_in=webhook2_in, site_id=site2.id)

    assert webhook1.site_id == site1.id
    assert webhook2.site_id == site2.id


def test_webhook_all_event_types(db: Session) -> None:
    """Test creating a webhook with all event types enabled."""
    moderator = _create_test_user(db)
    site = _create_test_site(db, moderator=moderator)

    webhook_in = WebhookCreate(
        site_uuid=site.uuid,
        event_spec=WebhookEventSpec(
            content=WebhookSiteEvent(
                new_question=True,
                new_answer=True,
                new_submission=True,
            )
        ),
        secret="all-events-secret",
        callback_url="https://example.com/all-events",
    )

    webhook = crud.webhook.create_with_site(db, obj_in=webhook_in, site_id=site.id)

    assert webhook is not None
