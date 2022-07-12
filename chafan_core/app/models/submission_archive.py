from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.db.base_class import Base
from chafan_core.utils.constants import editor_T

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class SubmissionArchive(Base):
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String)
    description_text = Column(String)
    description_editor: editor_T = Column(String)
    created_at = Column(DateTime(timezone=True), nullable=False)
    submission_id = Column(
        Integer, ForeignKey("submission.id"), nullable=False, index=True
    )
    submission = relationship("Submission", back_populates="archives")
    topic_uuids = Column(JSON)
