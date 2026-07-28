from typing import Any, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.models.channel import Channel
from chafan_core.app.schemas.channel import ChannelCreate, FeedbackSubjectT


def get(db: Session, id: Any) -> Optional[Channel]:
    return db.query(Channel).filter(Channel.id == id).first()


def add_user(db: Session, *, db_obj: Channel, user: models.User) -> Channel:
    db_obj.members.append(user)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def find_channel(
    db: Session,
    *,
    admin_user: models.User,
    with_user: models.User,
    subject: FeedbackSubjectT,
) -> Optional[models.Channel]:
    stream = db.query(Channel).filter_by(
        is_private=True,
        admin_id=admin_user.id,
        private_with_user_id=with_user.id,
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
    db: Session,
    *,
    host_user: models.User,
    with_user: models.User,
    obj_in: ChannelCreate,
) -> Channel:
    channel = find_channel(
        db, admin_user=host_user, with_user=with_user, subject=obj_in.subject
    )
    if channel is None:
        channel = find_channel(
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
                channel.site_creation_subject = jsonable_encoder(obj_in.subject.site_in)
        db.add(channel)
        db.flush()
        db.refresh(channel)
        channel.members.append(host_user)
        channel.members.append(with_user)
        db.flush()
        db.refresh(channel)
    return channel
