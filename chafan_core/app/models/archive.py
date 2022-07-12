from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from chafan_core.db.base_class import Base
from chafan_core.utils.constants import editor_T

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Archive(Base):
    id = Column(Integer, primary_key=True, index=True)
    body = Column(String, nullable=False)
    editor: editor_T = Column(String, nullable=False, server_default="wysiwyg")
    created_at = Column(DateTime(timezone=True), nullable=False)
    answer_id = Column(Integer, ForeignKey("answer.id"), nullable=False, index=True)
    answer = relationship("Answer", back_populates="archives")
