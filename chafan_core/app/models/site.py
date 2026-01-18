import datetime
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import (
    CHAR,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403

site_topics = Table(
    "site_topics",
    Base.metadata,
    Column("site_id", Integer, ForeignKey("site.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)


class Site(Base):
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = Column(
        CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False
    )
    subdomain: Mapped[str] = Column(String, nullable=False, unique=True, index=True)
    name: Mapped[str] = Column(String, unique=True, nullable=False)
    created_at: Mapped[datetime.datetime] = Column(DateTime(timezone=True), nullable=False)
    description: Mapped[Optional[str]] = Column(String)
    topics: Mapped[List["Topic"]] = relationship("Topic", secondary=site_topics)

    category_topic_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("topic.id"), index=True, nullable=True
    )
    category_topic: Mapped[Optional["Topic"]] = relationship("Topic")

    # Site policies
    public_readable: Mapped[bool] = Column(Boolean, default=False)
    public_writable_question: Mapped[bool] = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
    public_writable_submission: Mapped[bool] = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
    public_writable_answer: Mapped[bool] = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
    public_writable_comment: Mapped[bool] = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
    addable_member: Mapped[bool] = Column(
        Boolean, default=True, server_default="true", nullable=False
    )
    create_question_coin_deduction: Mapped[int] = Column(
        Integer, default=2, server_default="2", nullable=False
    )
    create_submission_coin_deduction: Mapped[int] = Column(
        Integer, default=2, server_default="2", nullable=False
    )
    create_suggestion_coin_deduction: Mapped[int] = Column(
        Integer, default=1, server_default="1", nullable=False
    )
    upvote_answer_coin_deduction: Mapped[int] = Column(
        Integer, default=2, server_default="2", nullable=False
    )
    upvote_question_coin_deduction: Mapped[int] = Column(
        Integer, default=1, server_default="1", nullable=False
    )
    upvote_submission_coin_deduction: Mapped[int] = Column(
        Integer, default=1, server_default="1", nullable=False
    )

    moderator_id: Mapped[int] = Column(
        Integer, ForeignKey("user.id"), nullable=False, server_default="1"
    )
    moderator: Mapped["User"] = relationship("User", back_populates="moderated_sites")
    questions: Mapped[List["Question"]] = relationship(
        "Question",
        back_populates="site",
        order_by="desc(Question.created_at)",
        lazy="dynamic",
    )
    submissions: Mapped[List["Submission"]] = relationship(
        "Submission",
        back_populates="site",
        order_by="desc(Submission.created_at)",
        lazy="dynamic",
    )
    profiles: Mapped[List["Profile"]] = relationship("Profile", back_populates="site")
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="site")
    answers: Mapped[List["Answer"]] = relationship("Answer", back_populates="site")

    applications: Mapped[List["Application"]] = relationship(
        "Application",
        back_populates="applied_site",
        order_by="Application.created_at.desc()",
    )

    # Approval conditions
    auto_approval: Mapped[bool] = Column(
        Boolean, default=True, server_default="true", nullable=False
    )
    min_karma_for_application: Mapped[Optional[int]] = Column(Integer)
    email_domain_suffix_for_application: Mapped[Optional[str]] = Column(String)

    webhooks: Mapped[List["Webhook"]] = relationship(
        "Webhook", back_populates="site", order_by="Webhook.updated_at.desc()"
    )

    keywords: Mapped[Optional[Any]] = Column(JSON)
