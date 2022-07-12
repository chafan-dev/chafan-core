from typing import TYPE_CHECKING, List, Optional

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
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.utils.base import UUID_LENGTH
from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403

site_topics = Table(
    "site_topics",
    Base.metadata,
    Column("site_id", Integer, ForeignKey("site.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)


class Site(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)
    subdomain = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    description = Column(String)
    topics: List["Topic"] = relationship("Topic", secondary=site_topics)  # type: ignore

    category_topic_id = Column(
        Integer, ForeignKey("topic.id"), index=True, nullable=True
    )
    category_topic: Optional["Topic"] = relationship("Topic")  # type: ignore

    # Site policies
    public_readable = Column(Boolean, default=False)
    public_writable_question = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
    public_writable_submission = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
    public_writable_answer = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
    public_writable_comment = Column(
        Boolean, default=False, server_default="false", nullable=False
    )
    addable_member = Column(
        Boolean, default=True, server_default="true", nullable=False
    )
    create_question_coin_deduction = Column(
        Integer, default=2, server_default="2", nullable=False
    )
    create_submission_coin_deduction = Column(
        Integer, default=2, server_default="2", nullable=False
    )
    create_suggestion_coin_deduction = Column(
        Integer, default=1, server_default="1", nullable=False
    )
    upvote_answer_coin_deduction = Column(
        Integer, default=2, server_default="2", nullable=False
    )
    upvote_question_coin_deduction = Column(
        Integer, default=1, server_default="1", nullable=False
    )
    upvote_submission_coin_deduction = Column(
        Integer, default=1, server_default="1", nullable=False
    )

    moderator_id = Column(
        Integer, ForeignKey("user.id"), nullable=False, server_default="1"
    )
    moderator = relationship("User", back_populates="moderated_sites")
    questions: List["Question"] = relationship(  # type: ignore
        "Question",
        back_populates="site",
        order_by="desc(Question.created_at)",
        lazy="dynamic",
    )
    submissions: List["Submission"] = relationship(  # type: ignore
        "Submission",
        back_populates="site",
        order_by="desc(Submission.created_at)",
        lazy="dynamic",
    )
    profiles: List["Profile"] = relationship("Profile", back_populates="site")  # type: ignore
    comments: List["Comment"] = relationship("Comment", back_populates="site")  # type: ignore
    answers: List["Answer"] = relationship("Answer", back_populates="site")  # type: ignore

    applications: List["Application"] = relationship(  # type: ignore
        "Application",
        back_populates="applied_site",
        order_by="Application.created_at.desc()",
    )

    # Approval conditions
    auto_approval = Column(Boolean, default=True, server_default="true", nullable=False)
    min_karma_for_application = Column(Integer)
    email_domain_suffix_for_application = Column(String)

    webhooks: List["Webhook"] = relationship(  # type: ignore
        "Webhook", back_populates="site", order_by="Webhook.updated_at.desc()"
    )

    keywords: List[str] = Column(JSON)  # type: ignore
