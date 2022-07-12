from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Webhook(Base):
    id = Column(Integer, primary_key=True, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    site_id = Column(Integer, ForeignKey("site.id"), nullable=False, index=True)
    site: "Site" = relationship("Site", back_populates="webhooks")  # type: ignore

    enabled = Column(Boolean, default=True, nullable=False)
    event_spec = Column(JSON, nullable=False)
    secret = Column(String, nullable=False)
    callback_url = Column(String, nullable=False)
