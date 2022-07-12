from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import JSON, Enum

from chafan_core.utils.base import TaskStatus
from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Task(Base):
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    initiator_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    initiator = relationship("User", back_populates="initiated_tasks")
    task_definition = Column(JSON, nullable=False)

    status = Column(Enum(TaskStatus), nullable=False)
