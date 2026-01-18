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

    cancelled: Mapped[bool] = Column(
        Boolean, server_default="false", default=False, nullable=False
    )
    submission_id: Mapped[int] = Column(
        Integer, ForeignKey("submission.id"), index=True
    )
    submission: Mapped["Submission"] = relationship(
        "Submission", foreign_keys=[submission_id]
    )
    voter_id: Mapped[int] = Column(Integer, ForeignKey("user.id"), index=True)
    voter: Mapped["User"] = relationship("User", foreign_keys=[voter_id])


class Submission(Base):
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = Column(
        CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False
    )

    site_id: Mapped[int] = Column(
        Integer, ForeignKey("site.id"), nullable=False, index=True
    )
    site: Mapped["Site"] = relationship("Site", back_populates="submissions")

    author_id: Mapped[int] = Column(
        Integer, ForeignKey("user.id"), nullable=False, index=True
    )
    author: Mapped["User"] = relationship(
        "User", back_populates="submissions", foreign_keys=[author_id]
    )

    contributors: Mapped[List["User"]] = relationship(
        "User",
        secondary=submission_contributors,
        backref=backref(
            "contributed_submissions",
            lazy="dynamic",
            order_by="Submission.created_at.desc()",
        ),
    )

    topics: Mapped[List["Topic"]] = relationship(
        "Topic",
        secondary=submission_topics,
        backref=backref(
            "submissions", lazy="dynamic", order_by="Submission.created_at.desc()"
        ),
    )

    title: Mapped[str] = Column(String, nullable=False)

    # description XOR url -- see HackerNews
    description: Mapped[Optional[str]] = Column(String)
    description_text: Mapped[Optional[str]] = Column(String)
    description_editor: Mapped[str] = Column(String, nullable=False, default="tiptap")

    url: Mapped[Optional[str]] = Column(String)

    keywords: Mapped[Optional[Any]] = Column(JSON)

    created_at: Mapped[datetime.datetime] = Column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime.datetime] = Column(DateTime(timezone=True), nullable=False)
    is_hidden: Mapped[bool] = Column(
        Boolean, server_default="false", nullable=False, default=False
    )

    comments: Mapped[List["Comment"]] = relationship(
        "Comment", back_populates="submission", order_by="Comment.created_at.asc()"
    )

    upvotes_count: Mapped[int] = Column(
        Integer, default=0, server_default="0", nullable=False
    )

    archives: Mapped[List["SubmissionArchive"]] = relationship(
        "SubmissionArchive",
        back_populates="submission",
        order_by="SubmissionArchive.created_at.desc()",
    )
    submission_suggestions: Mapped[List["SubmissionSuggestion"]] = relationship(
        "SubmissionSuggestion",
        back_populates="submission",
        order_by="SubmissionSuggestion.created_at.desc()",
    )

    reports: Mapped[List["Report"]] = relationship(
        "Report", back_populates="submission", order_by="Report.created_at.asc()"
    )
