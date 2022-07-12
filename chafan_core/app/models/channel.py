from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403

channel_members = Table(
    "channel_members",
    Base.metadata,
    Column("channel_id", Integer, ForeignKey("channel.id")),
    Column("user_id", Integer, ForeignKey("user.id")),
)


class Channel(Base):
    id = Column(Integer, primary_key=True, index=True)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # TODO: deprecate
    admin_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    admin = relationship("User", foreign_keys=[admin_id])
    # TODO: deprecate
    name = Column(String, nullable=False)
    messages: List["Message"] = relationship("Message", back_populates="channel", order_by="Message.id")  # type: ignore
    # TODO: deprecate
    is_private = Column(Boolean, default=False, nullable=False, server_default="false")

    private_with_user_id = Column(Integer, ForeignKey("user.id"), index=True)
    private_with_user = relationship("User", foreign_keys=[private_with_user_id])

    # TODO: deprecate
    members: List["User"] = relationship(  # type: ignore
        "User",
        secondary=channel_members,
        backref=backref("channels", order_by="Channel.updated_at.desc()"),
    )

    feedback_subject_id = Column(Integer, ForeignKey("feedback.id"), index=True)
    feedback_subject = relationship("Feedback", foreign_keys=[feedback_subject_id])

    site_creation_subject_subdomain = Column(String, index=True)
    site_creation_subject = Column(JSON)
