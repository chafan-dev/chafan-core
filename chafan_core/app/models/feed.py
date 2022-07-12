from typing import TYPE_CHECKING, Optional

from sqlalchemy import CHAR, Column, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import UniqueConstraint

from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Feed(Base):
    id = Column(Integer, primary_key=True, index=True)
    receiver_id = Column(Integer, ForeignKey("user.id"), index=True, nullable=False)
    receiver = relationship("User", foreign_keys=[receiver_id])
    activity_id = Column(Integer, ForeignKey("activity.id"), index=True, nullable=False)
    activity: "Activity" = relationship("Activity", foreign_keys=[activity_id])  # type: ignore

    subject_user_uuid = Column(
        CHAR(length=UUID_LENGTH), ForeignKey("user.uuid"), nullable=True
    )
    subject_user: Optional["User"] = relationship("User", foreign_keys=[subject_user_uuid])  # type: ignore

    __table_args__ = (UniqueConstraint("activity_id", "receiver_id"),)
