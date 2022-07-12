import datetime
from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.models.invitation import Invitation
from chafan_core.app.schemas.user import UserInvite


class CRUDComment(object):
    def get(self, db: Session, *, id: int) -> Optional[Invitation]:
        return db.query(Invitation).filter_by(id=id).first()

    def create_invitation(
        self,
        db: Session,
        *,
        user_invite: UserInvite,
        is_sent: bool,
        inviter: models.User,
    ) -> Optional[Invitation]:
        user_id = None
        site_id = None
        user = crud.user.get_by_uuid(db, uuid=user_invite.user_uuid)
        if user is None:
            return None
        user_id = user.id
        site = crud.site.get_by_uuid(db, uuid=user_invite.site_uuid)
        if site is None:
            return None
        site_id = site.id
        db_obj = Invitation(
            created_at=datetime.datetime.now(tz=datetime.timezone.utc),
            inviter_id=inviter.id,
            invited_user_id=user_id,
            invited_to_site_id=site_id,
            is_sent=is_sent,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_email(self, db: Session, *, email: str) -> Optional[Invitation]:
        return db.query(Invitation).filter_by(invited_email=email).first()


invitation = CRUDComment()
