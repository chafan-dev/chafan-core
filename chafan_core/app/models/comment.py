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
from sqlalchemy.orm import relationship

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

    cancelled = Column(Boolean, server_default="false", default=False, nullable=False)
    comment_id = Column(Integer, ForeignKey("comment.id"), index=True)
    comment = relationship("Comment", foreign_keys=[comment_id])
    voter_id = Column(Integer, ForeignKey("user.id"), index=True)
    voter = relationship("User", foreign_keys=[voter_id])


class Comment(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)

    editor: editor_T = Column(String, nullable=False, default="tiptap")  # type: ignore

    author_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    author = relationship("User", back_populates="comments")

    site_id = Column(Integer, ForeignKey("site.id"), index=True)
    site: Optional["Site"] = relationship("Site", back_populates="comments")  # type: ignore

    question_id = Column(Integer, ForeignKey("question.id"), index=True)
    question: Optional["Question"] = relationship("Question", back_populates="comments")  # type: ignore

    submission_id = Column(Integer, ForeignKey("submission.id"), index=True)
    submission: Optional["Submission"] = relationship("Submission", back_populates="comments")  # type: ignore

    article_id = Column(Integer, ForeignKey("article.id"), index=True)
    article: Optional["Article"] = relationship("Article", back_populates="comments")  # type: ignore

    answer_id = Column(Integer, ForeignKey("answer.id"), index=True)
    answer: Optional["Answer"] = relationship("Answer", back_populates="comments")  # type: ignore

    parent_comment_id = Column(Integer, ForeignKey("comment.id"), index=True)
    parent_comment: Optional["Comment"] = relationship(
        "Comment", back_populates="child_comments", remote_side=[id]
    )  # type: ignore

    # content fields
    body = Column(String, nullable=False)
    body_text = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    is_deleted = Column(Boolean, default=False, server_default="false", nullable=False)

    child_comments: List["Comment"] = relationship("Comment", back_populates="parent_comment", order_by="Comment.created_at.asc()")  # type: ignore
    reports: List["Report"] = relationship("Report", back_populates="comment", order_by="Report.created_at.asc()")  # type: ignore

    shared_to_timeline = Column(
        Boolean, server_default="false", nullable=False, default=False
    )

    upvotes_count = Column(Integer, default=0, server_default="0", nullable=False)
