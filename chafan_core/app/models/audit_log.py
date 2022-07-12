from typing import TYPE_CHECKING

from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.utils.base import UUID_LENGTH
from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class AuditLog(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    user = relationship("User", back_populates="audit_logs")
    ipaddr = Column(String, index=True, nullable=False)

    api = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    request_info = Column(JSON)
