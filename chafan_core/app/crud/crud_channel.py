from typing import Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.channel import Channel
from chafan_core.app.schemas.channel import ChannelCreate, ChannelUpdate, FeedbackSubjectT


class CRUDChannel(CRUDBase[Channel, ChannelCreate, ChannelUpdate]):
    def add_user(self, db: Session, *, db_obj: Channel, user: models.User) -> Channel:
        db_obj.members.append(user)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def find_channel(
        self,
        db: Session,
        *,
        admin_user: models.User,
        with_user: models.User,
        subject: FeedbackSubjectT
    ) -> Optional[models.Channel]:
        stream = db.query(Channel).filter_by(
            is_private=True, admin_id=admin_user.id, private_with_user_id=with_user.id,
        )
        if subject is not None:
            if subject.type == "feedback":
                stream = stream.filter_by(feedback_subject_id=subject.id)
            if subject.type == "site_creation":
                stream = stream.filter_by(
                    site_creation_subject_subdomain=subject.site_in.subdomain
                )
        return stream.first()

    def get_or_create_private_channel_with(
        self,
        db: Session,
        *,
        host_user: models.User,
        with_user: models.User,
        obj_in: ChannelCreate
    ) -> Channel:
        channel = self.find_channel(
            db, admin_user=host_user, with_user=with_user, subject=obj_in.subject
        )
        if channel is None:
            channel = self.find_channel(
                db, admin_user=with_user, with_user=host_user, subject=obj_in.subject
            )
        if channel is None:
            channel = Channel(
                name="",
                admin_id=host_user.id,
                is_private=True,
                private_with_user_id=with_user.id,
            )
            if obj_in.subject:
                if obj_in.subject.type == "feedback":
                    channel.feedback_subject_id = obj_in.subject.id
                if obj_in.subject.type == "site_creation":
                    channel.site_creation_subject_subdomain = (
                        obj_in.subject.site_in.subdomain
                    )
                    channel.site_creation_subject = jsonable_encoder(
                        obj_in.subject.site_in
                    )
            db.add(channel)
            db.commit()
            db.refresh(channel)
            channel.members.append(host_user)
            channel.members.append(with_user)
            db.commit()
            db.refresh(channel)
        return channel


channel = CRUDChannel(Channel)
