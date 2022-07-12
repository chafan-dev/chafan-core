from typing import TYPE_CHECKING

from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from chafan_core.utils.base import UUID_LENGTH
from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class InvitationLink(Base):
    id = Column(Integer, primary_key=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expired_at = Column(DateTime(timezone=True), nullable=False)

    inviter_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    inviter = relationship("User", foreign_keys=[inviter_id])

    invited_to_site_id = Column(Integer, ForeignKey("site.id"), nullable=True)
    invited_to_site = relationship("Site", foreign_keys=[invited_to_site_id])

    remaining_quota = Column(Integer, nullable=False)
