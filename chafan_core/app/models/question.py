import datetime
from typing import TYPE_CHECKING, Any, List, Optional

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
from sqlalchemy.orm import Mapped, backref, relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH
from chafan_core.utils.constants import editor_T

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

    cancelled: Mapped[bool] = Column(
        Boolean, server_default="false", default=False, nullable=False
    )
    question_id: Mapped[int] = Column(Integer, ForeignKey("question.id"), index=True)
    question: Mapped["Question"] = relationship("Question", foreign_keys=[question_id])
    voter_id: Mapped[int] = Column(Integer, ForeignKey("user.id"), index=True)
    voter: Mapped["User"] = relationship("User", foreign_keys=[voter_id])


class Question(Base):
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = Column(
        CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False
    )

    site_id: Mapped[int] = Column(
        Integer, ForeignKey("site.id"), nullable=False, index=True
    )
    site: Mapped["Site"] = relationship("Site", back_populates="questions")
    author_id: Mapped[int] = Column(
        Integer, ForeignKey("user.id"), nullable=False, index=True
    )
    author: Mapped["User"] = relationship(
        "User", back_populates="questions", foreign_keys=[author_id]
    )

    editor_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("user.id"), nullable=True, index=True
    )
    editor: Mapped[Optional["User"]] = relationship(
        "User", back_populates="questions", foreign_keys=[editor_id]
    )

    topics: Mapped[List["Topic"]] = relationship(
        "Topic",
        secondary=question_topics,
        backref=backref(
            "questions", lazy="dynamic", order_by="Question.created_at.desc()"
        ),
    )

    # content fields
    title: Mapped[str] = Column(String, nullable=False)
    description: Mapped[Optional[str]] = Column(String)
    description_text: Mapped[Optional[str]] = Column(String)
    description_editor: Mapped[str] = Column(String, nullable=False, default="tiptap")

    created_at: Mapped[datetime.datetime] = Column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime.datetime] = Column(DateTime(timezone=True), nullable=False)

    # unlisted
    is_hidden: Mapped[bool] = Column(
        Boolean, server_default="false", nullable=False, default=False
    )

    keywords: Mapped[Optional[Any]] = Column(JSON)

    answers: Mapped[List["Answer"]] = relationship(
        "Answer", back_populates="question", order_by="Answer.updated_at.desc()"
    )
    comments: Mapped[List["Comment"]] = relationship(
        "Comment", back_populates="question", order_by="Comment.created_at.asc()"
    )

    is_placed_at_home: Mapped[bool] = Column(
        Boolean,
        server_default="false",
        default=False,
        nullable=False,
        index=True,
    )

    upvotes_count: Mapped[int] = Column(
        Integer, default=0, server_default="0", nullable=False
    )

    archives: Mapped[List["QuestionArchive"]] = relationship(
        "QuestionArchive",
        back_populates="question",
        order_by="QuestionArchive.created_at.desc()",
    )

    reports: Mapped[List["Report"]] = relationship(
        "Report", back_populates="question", order_by="Report.created_at.asc()"
    )
