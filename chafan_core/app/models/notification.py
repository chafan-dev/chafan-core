from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Notification(Base):
    id = Column(Integer, primary_key=True, index=True)
    receiver_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    receiver = relationship("User", back_populates="notifications")

    # Change to non-null after deprecation
    event_json = Column(String)
    created_at = Column(DateTime(timezone=True), nullable=False)

    is_read = Column(Boolean, default=False, server_default="false", nullable=False)
    is_delivered = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
