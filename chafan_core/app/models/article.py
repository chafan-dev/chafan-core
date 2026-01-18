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

    cancelled: Mapped[bool] = Column(
        Boolean, server_default="false", default=False, nullable=False
    )
    article_id: Mapped[int] = Column(Integer, ForeignKey("article.id"), index=True)
    article: Mapped["Article"] = relationship("Article", foreign_keys=[article_id])
    voter_id: Mapped[int] = Column(Integer, ForeignKey("user.id"), index=True)
    voter: Mapped["User"] = relationship("User", foreign_keys=[voter_id])


class Article(Base):
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = Column(
        CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False
    )
    author_id: Mapped[int] = Column(
        Integer, ForeignKey("user.id"), nullable=False, index=True
    )
    author: Mapped["User"] = relationship(
        "User", back_populates="articles", foreign_keys=[author_id]
    )
    article_column_id: Mapped[int] = Column(
        Integer, ForeignKey("articlecolumn.id"), nullable=False, index=True
    )
    article_column: Mapped["ArticleColumn"] = relationship(
        "ArticleColumn", back_populates="articles", foreign_keys=[article_column_id]
    )

    topics: Mapped[List["Topic"]] = relationship(
        "Topic",
        secondary=article_topics,
        backref=backref(
            "articles", lazy="dynamic", order_by="Article.created_at.desc()"
        ),
    )

    # content fields
    title: Mapped[str] = Column(String, nullable=False)
    title_draft: Mapped[Optional[str]] = Column(String)

    body: Mapped[str] = Column(String, nullable=False)
    body_text: Mapped[Optional[str]] = Column(String)

    # Not null only if is_published is `True`, in which case it might contain a working draft version.
    body_draft: Mapped[Optional[str]] = Column(String)

    editor: Mapped[str] = Column(String, nullable=False, server_default="wysiwyg")

    created_at: Mapped[datetime.datetime] = Column(DateTime(timezone=True), nullable=False)
    initial_published_at: Mapped[Optional[datetime.datetime]] = Column(
        DateTime(timezone=True)
    )
    updated_at: Mapped[Optional[datetime.datetime]] = Column(
        DateTime(timezone=True)
    )  # published_at
    draft_saved_at: Mapped[Optional[datetime.datetime]] = Column(DateTime(timezone=True))
    draft_editor: Mapped[str] = Column(String, nullable=False, server_default="wysiwyg")

    is_published: Mapped[bool] = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
    is_deleted: Mapped[bool] = Column(
        Boolean, default=False, server_default="false", nullable=False
    )

    comments: Mapped[List["Comment"]] = relationship(
        "Comment", back_populates="article", order_by="Comment.created_at.asc()"
    )

    upvotes_count: Mapped[int] = Column(
        Integer, default=0, server_default="0", nullable=False
    )

    archives: Mapped[List["ArticleArchive"]] = relationship(
        "ArticleArchive",
        back_populates="article",
        order_by="ArticleArchive.created_at.desc()",
    )

    visibility: Mapped[ContentVisibility] = Column(
        Enum(ContentVisibility), nullable=False, server_default="ANYONE"
    )

    keywords: Mapped[Optional[Any]] = Column(JSON)

    featured_at: Mapped[Optional[datetime.datetime]] = Column(DateTime(timezone=True))

    reports: Mapped[List["Report"]] = relationship(
        "Report", back_populates="article", order_by="Report.created_at.asc()"
    )
