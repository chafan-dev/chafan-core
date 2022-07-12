from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import LargeBinary

from chafan_core.utils.constants import feedback_status_T
from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Feedback(Base):
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    user: Optional["User"] = relationship("User", back_populates="feedbacks", foreign_keys=[user_id])  # type: ignore
    user_email = Column(String)  # User-provided email if not logged in
    created_at = Column(DateTime(timezone=True), nullable=False)
    status: feedback_status_T = Column(String, server_default="sent", nullable=False)  # type: ignore
    location_url = Column(String)

    description = Column(String, nullable=False)
    screenshot_blob = Column(LargeBinary)
