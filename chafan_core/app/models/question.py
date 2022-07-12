from typing import TYPE_CHECKING, List

from sqlalchemy import (
    CHAR,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.utils.base import UUID_LENGTH
from chafan_core.utils.constants import editor_T
from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403

question_topics = Table(
    "question_topics",
    Base.metadata,
    Column("question_id", Integer, ForeignKey("question.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)


class QuestionUpvotes(Base):
    __table_args__ = (
        UniqueConstraint("question_id", "voter_id"),
        PrimaryKeyConstraint("question_id", "voter_id"),
    )

    cancelled = Column(Boolean, server_default="false", default=False, nullable=False)
    question_id = Column(Integer, ForeignKey("question.id"), index=True)
    question = relationship("Question", foreign_keys=[question_id])
    voter_id = Column(Integer, ForeignKey("user.id"), index=True)
    voter = relationship("User", foreign_keys=[voter_id])


class Question(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)

    site_id = Column(Integer, ForeignKey("site.id"), nullable=False, index=True)
    site: "Site" = relationship("Site", back_populates="questions")  # type: ignore
    author_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    author: "User" = relationship("User", back_populates="questions", foreign_keys=[author_id])  # type: ignore

    editor_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True)
    editor = relationship("User", back_populates="questions", foreign_keys=[editor_id])

    topics: List["Topic"] = relationship(  # type: ignore
        "Topic",
        secondary=question_topics,
        backref=backref(
            "questions", lazy="dynamic", order_by="Question.created_at.desc()"
        ),
    )

    # content fields
    title = Column(String, nullable=False)
    description = Column(String)
    description_text = Column(String)
    description_editor: editor_T = Column(String, nullable=False, default="tiptap")  # type: ignore
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    # unlisted
    is_hidden = Column(Boolean, server_default="false", nullable=False, default=False)

    keywords = Column(JSON)

    answers: List["Answer"] = relationship(  # type: ignore
        "Answer", back_populates="question", order_by="Answer.updated_at.desc()"
    )
    comments: List["Comment"] = relationship(  # type: ignore
        "Comment", back_populates="question", order_by="Comment.created_at.asc()"
    )

    is_placed_at_home = Column(
        Boolean, server_default="false", default=False, nullable=False, index=True,
    )

    upvotes_count = Column(Integer, default=0, server_default="0", nullable=False)

    archives: List["QuestionArchive"] = relationship("QuestionArchive", back_populates="question", order_by="QuestionArchive.created_at.desc()")  # type: ignore

    reports: List["Report"] = relationship("Report", back_populates="question", order_by="Report.created_at.asc()")  # type: ignore
