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
from sqlalchemy.sql.sqltypes import JSON, Enum

from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH, ContentVisibility
from chafan_core.utils.constants import editor_T

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Answer_Upvotes(Base):
    __table_args__ = (
        UniqueConstraint("answer_id", "voter_id"),
        PrimaryKeyConstraint("answer_id", "voter_id"),
    )

    cancelled = Column(Boolean, server_default="false", default=False, nullable=False)
    answer_id = Column(Integer, ForeignKey("answer.id"), index=True)
    answer = relationship("Answer", foreign_keys=[answer_id])
    voter_id = Column(Integer, ForeignKey("user.id"), index=True)
    voter = relationship("User", foreign_keys=[voter_id])


answer_contributors = Table(
    "answer_contributors",
    Base.metadata,
    Column("answer_id", Integer, ForeignKey("answer.id")),
    Column("user_id", Integer, ForeignKey("user.id")),
)


class Answer(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)
    author_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    author: "User" = relationship("User", back_populates="answers")  # type: ignore
    site_id = Column(Integer, ForeignKey("site.id"), nullable=False, index=True)
    site: "Site" = relationship("Site", back_populates="answers")  # type: ignore
    question_id = Column(Integer, ForeignKey("question.id"), nullable=False, index=True)
    question: "Question" = relationship("Question", back_populates="answers")  # type: ignore

    upvotes_count = Column(Integer, default=0, nullable=False)

    is_hidden_by_moderator = Column(Boolean, server_default="false", nullable=False)

    # If not `is_published`, `body` is the author-only draft.
    # Otherwise, `body` is the latest published text.
    body = Column(String, nullable=False)

    body_prerendered_text = Column(String, nullable=False)
    keywords = Column(JSON)

    # Not null only if is_published is `True`, in which case it might contain a working draft version.
    body_draft = Column(String)

    editor: editor_T = Column(String, nullable=False, server_default="wysiwyg")  # type: ignore

    draft_saved_at = Column(DateTime(timezone=True))
    draft_editor: editor_T = Column(String, nullable=False, server_default="wysiwyg")  # type: ignore

    # Whether `body` contains the latest published version
    is_published = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Whether `body` contains the latest published version
    is_deleted = Column(Boolean, default=False, server_default="false", nullable=False)
    # Time of the latest publication
    updated_at = Column(DateTime(timezone=True), nullable=False)

    archives: List["Archive"] = relationship("Archive", back_populates="answer", order_by="Archive.created_at.desc()")  # type: ignore

    comments: List["Comment"] = relationship("Comment", back_populates="answer", order_by="Comment.created_at.asc()")  # type: ignore

    # If in public site: World visible > registered user visible > [my friends visible -- in future]
    # If in private site: site members visible > [my friends visible -- in future]
    # https://stackoverflow.com/questions/37848815/sqlalchemy-postgresql-enum-does-not-create-type-on-db-migrate
    visibility: ContentVisibility = Column(
        Enum(ContentVisibility), nullable=False, server_default="ANYONE"
    )  # type: ignore

    suggest_edits: List["AnswerSuggestEdit"] = relationship("AnswerSuggestEdit", back_populates="answer", order_by="AnswerSuggestEdit.created_at.desc()")  # type: ignore

    contributors: List["User"] = relationship(  # type: ignore
        "User",
        secondary=answer_contributors,
        backref=backref(
            "contributed_answers",
            lazy="dynamic",
            order_by="Answer.updated_at.desc()",
        ),
    )

    featured_at = Column(DateTime(timezone=True))

    reports: List["Report"] = relationship("Report", back_populates="answer", order_by="Report.created_at.asc()")  # type: ignore
