import datetime
from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models import InvitationLink
from chafan_core.app.schemas.invitation_link import InvitationLinkCreate, InvitationLinkUpdate


class CRUDInvitationLink(
    CRUDBase[InvitationLink, InvitationLinkCreate, InvitationLinkUpdate]
):
    def create_invitation(
        self, db: Session, *, invited_to_site_id: Optional[int], inviter: models.User,
    ) -> InvitationLink:
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        db_obj = InvitationLink(
            uuid=self.get_unique_uuid(db),
            created_at=utc_now,
            expired_at=utc_now + datetime.timedelta(days=7),
            inviter_id=inviter.id,
            invited_to_site_id=invited_to_site_id,
            remaining_quota=100,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


invitation_link = CRUDInvitationLink(InvitationLink)
