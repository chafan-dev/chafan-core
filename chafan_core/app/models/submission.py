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

from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH
from chafan_core.utils.constants import editor_T

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403

submission_topics = Table(
    "submission_topics",
    Base.metadata,
    Column("submission_id", Integer, ForeignKey("submission.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)

submission_contributors = Table(
    "submission_contributors",
    Base.metadata,
    Column("submission_id", Integer, ForeignKey("submission.id")),
    Column("user_id", Integer, ForeignKey("user.id")),
)


class SubmissionUpvotes(Base):
    __table_args__ = (
        UniqueConstraint("submission_id", "voter_id"),
        PrimaryKeyConstraint("submission_id", "voter_id"),
    )

    cancelled = Column(Boolean, server_default="false", default=False, nullable=False)
    submission_id = Column(Integer, ForeignKey("submission.id"), index=True)
    submission = relationship("Submission", foreign_keys=[submission_id])
    voter_id = Column(Integer, ForeignKey("user.id"), index=True)
    voter = relationship("User", foreign_keys=[voter_id])


class Submission(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)

    site_id = Column(Integer, ForeignKey("site.id"), nullable=False, index=True)
    site: "Site" = relationship("Site", back_populates="submissions")  # type: ignore

    author_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    author: "User" = relationship(
        "User", back_populates="submissions", foreign_keys=[author_id]
    )  # type: ignore

    contributors: List["User"] = relationship(  # type: ignore
        "User",
        secondary=submission_contributors,
        backref=backref(
            "contributed_submissions",
            lazy="dynamic",
            order_by="Submission.created_at.desc()",
        ),
    )

    topics: List["Topic"] = relationship(  # type: ignore
        "Topic",
        secondary=submission_topics,
        backref=backref(
            "submissions", lazy="dynamic", order_by="Submission.created_at.desc()"
        ),
    )

    title = Column(String, nullable=False)

    # description XOR url -- see HackerNews
    description = Column(String)
    description_text = Column(String)
    description_editor: editor_T = Column(String, nullable=False, default="tiptap")  # type: ignore

    url = Column(String)

    keywords = Column(JSON)

    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    is_hidden = Column(Boolean, server_default="false", nullable=False, default=False)

    comments: List["Comment"] = relationship(  # type: ignore
        "Comment", back_populates="submission", order_by="Comment.created_at.asc()"
    )

    upvotes_count = Column(Integer, default=0, server_default="0", nullable=False)

    archives: List["SubmissionArchive"] = relationship("SubmissionArchive", back_populates="submission", order_by="SubmissionArchive.created_at.desc()")  # type: ignore
    submission_suggestions: List["SubmissionSuggestion"] = relationship("SubmissionSuggestion", back_populates="submission", order_by="SubmissionSuggestion.created_at.desc()")  # type: ignore

    reports: List["Report"] = relationship("Report", back_populates="submission", order_by="Report.created_at.asc()")  # type: ignore
