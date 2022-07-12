from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Invitation(Base):
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    inviter_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    inviter = relationship("User", foreign_keys=[inviter_id])

    invited_user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    invited_user = relationship("User", foreign_keys=[invited_user_id],)

    invited_to_site_id = Column(Integer, ForeignKey("site.id"), nullable=True)
    invited_to_site = relationship("Site", foreign_keys=[invited_to_site_id])
    is_sent = Column(Boolean, default=False, server_default="false", nullable=False)

    invitation_link = Column(String)
