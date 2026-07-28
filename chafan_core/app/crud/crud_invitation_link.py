import datetime
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.models import InvitationLink
from chafan_core.utils.base import get_uuid

logger = logging.getLogger(__name__)


def get(db: Session, id: Any) -> Optional[InvitationLink]:
    return db.query(InvitationLink).filter(InvitationLink.id == id).first()


def get_by_uuid(db: Session, *, uuid: str) -> Optional[InvitationLink]:
    return db.query(InvitationLink).filter_by(uuid=uuid).first()


def _get_unique_uuid(db: Session) -> str:
    while True:
        uuid = get_uuid()
        if get_by_uuid(db, uuid=uuid) is None:
            return uuid


def create_invitation(
    db: Session,
    *,
    invited_to_site_id: Optional[int],
    inviter: models.User,
) -> InvitationLink:
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    db_obj = InvitationLink(
        uuid=_get_unique_uuid(db),
        created_at=utc_now,
        expired_at=utc_now + datetime.timedelta(days=7),
        inviter_id=inviter.id,
        invited_to_site_id=invited_to_site_id,
        remaining_quota=100,
    )
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj
