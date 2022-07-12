from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Activity(Base):
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("site.id"), index=True)
    site: Optional["Site"] = relationship("Site", foreign_keys=[site_id])  # type: ignore
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    event_json = Column(String, nullable=False)
