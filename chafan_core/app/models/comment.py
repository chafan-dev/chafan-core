import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    CHAR,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, relationship

from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH
from chafan_core.utils.constants import editor_T

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class CommentUpvotes(Base):
    __table_args__ = (
        UniqueConstraint("comment_id", "voter_id"),
        PrimaryKeyConstraint("comment_id", "voter_id"),
    )

    cancelled: Mapped[bool] = Column(
        Boolean, server_default="false", default=False, nullable=False
    )
    comment_id: Mapped[int] = Column(Integer, ForeignKey("comment.id"), index=True)
    comment: Mapped["Comment"] = relationship("Comment", foreign_keys=[comment_id])
    voter_id: Mapped[int] = Column(Integer, ForeignKey("user.id"), index=True)
    voter: Mapped["User"] = relationship("User", foreign_keys=[voter_id])


class Comment(Base):
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = Column(
        CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False
    )

    editor: Mapped[str] = Column(String, nullable=False, default="tiptap")

    author_id: Mapped[int] = Column(
        Integer, ForeignKey("user.id"), nullable=False, index=True
    )
    author: Mapped["User"] = relationship("User", back_populates="comments")

    site_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("site.id"), index=True)
    site: Mapped[Optional["Site"]] = relationship("Site", back_populates="comments")

    question_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("question.id"), index=True
    )
    question: Mapped[Optional["Question"]] = relationship(
        "Question", back_populates="comments"
    )

    submission_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("submission.id"), index=True
    )
    submission: Mapped[Optional["Submission"]] = relationship(
        "Submission", back_populates="comments"
    )

    article_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("article.id"), index=True
    )
    article: Mapped[Optional["Article"]] = relationship(
        "Article", back_populates="comments"
    )

    answer_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("answer.id"), index=True
    )
    answer: Mapped[Optional["Answer"]] = relationship(
        "Answer", back_populates="comments"
    )

    parent_comment_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("comment.id"), index=True
    )
    parent_comment: Mapped[Optional["Comment"]] = relationship(
        "Comment", back_populates="child_comments", remote_side=[id]
    )

    # content fields
    body: Mapped[str] = Column(String, nullable=False)
    body_text: Mapped[str] = Column(String, nullable=False)

    created_at: Mapped[datetime.datetime] = Column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime.datetime] = Column(DateTime(timezone=True), nullable=False)
    is_deleted: Mapped[bool] = Column(
        Boolean, default=False, server_default="false", nullable=False
    )

    child_comments: Mapped[List["Comment"]] = relationship(
        "Comment", back_populates="parent_comment", order_by="Comment.created_at.asc()"
    )
    reports: Mapped[List["Report"]] = relationship(
        "Report", back_populates="comment", order_by="Report.created_at.asc()"
    )

    shared_to_timeline: Mapped[bool] = Column(
        Boolean, server_default="false", nullable=False, default=False
    )

    upvotes_count: Mapped[int] = Column(
        Integer, default=0, server_default="0", nullable=False
    )
