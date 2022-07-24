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
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql.sqltypes import JSON, Enum

from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH, ContentVisibility
from chafan_core.utils.constants import editor_T
from chafan_core.utils.validators import StrippedNonEmptyStr

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403

article_topics = Table(
    "article_topics",
    Base.metadata,
    Column("article_id", Integer, ForeignKey("article.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)


class ArticleUpvotes(Base):
    __table_args__ = (
        UniqueConstraint("article_id", "voter_id"),
        PrimaryKeyConstraint("article_id", "voter_id"),
    )

    cancelled = Column(Boolean, server_default="false", default=False, nullable=False)
    article_id = Column(Integer, ForeignKey("article.id"), index=True)
    article = relationship("Article", foreign_keys=[article_id])
    voter_id = Column(Integer, ForeignKey("user.id"), index=True)
    voter = relationship("User", foreign_keys=[voter_id])


class Article(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)
    author_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    author = relationship("User", back_populates="articles", foreign_keys=[author_id])
    article_column_id = Column(
        Integer, ForeignKey("articlecolumn.id"), nullable=False, index=True
    )
    article_column: "ArticleColumn" = relationship(
        "ArticleColumn", back_populates="articles", foreign_keys=[article_column_id]
    )  # type: ignore

    topics: List["Topic"] = relationship(  # type: ignore
        "Topic",
        secondary=article_topics,
        backref=backref(
            "articles", lazy="dynamic", order_by="Article.created_at.desc()"
        ),
    )

    # content fields
    title = Column(String, nullable=False)
    title_draft: Optional[StrippedNonEmptyStr] = Column(String)  # type: ignore

    body = Column(String, nullable=False)
    body_text = Column(String)

    # Not null only if is_published is `True`, in which case it might contain a working draft version.
    body_draft = Column(String)

    editor: editor_T = Column(String, nullable=False, server_default="wysiwyg")  # type: ignore

    created_at = Column(DateTime(timezone=True), nullable=False)
    initial_published_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))  # published_at
    draft_saved_at = Column(DateTime(timezone=True))
    draft_editor: editor_T = Column(String, nullable=False, server_default="wysiwyg")  # type: ignore

    is_published = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
    is_deleted = Column(Boolean, default=False, server_default="false", nullable=False)

    comments: List["Comment"] = relationship(  # type: ignore
        "Comment", back_populates="article", order_by="Comment.created_at.asc()"
    )

    upvotes_count = Column(Integer, default=0, server_default="0", nullable=False)

    archives: List["ArticleArchive"] = relationship(
        "ArticleArchive",
        back_populates="article",
        order_by="ArticleArchive.created_at.desc()",
    )  # type: ignore

    visibility = Column(
        Enum(ContentVisibility), nullable=False, server_default="ANYONE"
    )

    keywords: List[str] = Column(JSON)  # type: ignore

    featured_at = Column(DateTime(timezone=True))

    reports: List["Report"] = relationship("Report", back_populates="article", order_by="Report.created_at.asc()")  # type: ignore
