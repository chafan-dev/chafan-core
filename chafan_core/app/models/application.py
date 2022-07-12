from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Application(Base):
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    applicant_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    applicant: "User" = relationship("User", back_populates="applications")  # type: ignore

    applied_site_id = Column(Integer, ForeignKey("site.id"), nullable=False, index=True)
    applied_site: "Site" = relationship("Site", back_populates="applications")  # type: ignore

    pending = Column(Boolean, default=True, nullable=False)
