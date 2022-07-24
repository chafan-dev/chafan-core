from typing import TYPE_CHECKING, List

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import backref, relationship

from chafan_core.db.base_class import Base
from chafan_core.utils.constants import editor_T

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


question_archive_topics = Table(
    "question_archive_topics",
    Base.metadata,
    Column("question_archive_id", Integer, ForeignKey("questionarchive.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)


class QuestionArchive(Base):
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String)
    description_text = Column(String)
    description_editor: editor_T = Column(String)  # type: ignore

    created_at = Column(DateTime(timezone=True), nullable=False)
    question_id = Column(Integer, ForeignKey("question.id"), nullable=False, index=True)
    question = relationship("Question", back_populates="archives")
    editor_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True)
    editor = relationship("User", foreign_keys=[editor_id])
    topics: List["Topic"] = relationship(  # type: ignore
        "Topic",
        secondary=question_archive_topics,
        backref=backref(
            "question_archives",
            lazy="dynamic",
            order_by="QuestionArchive.created_at.desc()",
        ),
    )
