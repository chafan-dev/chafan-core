import datetime
from typing import TYPE_CHECKING, Any, List, Literal, Optional

from pydantic import AnyHttpUrl
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
from sqlalchemy.orm import Mapped, backref, relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.app.models.answer_suggest_edit import AnswerSuggestEdit
from chafan_core.app.models.audit_log import AuditLog
from chafan_core.app.models.coin_deposit import CoinDeposit
from chafan_core.app.models.coin_payment import CoinPayment
from chafan_core.app.models.feedback import Feedback
from chafan_core.app.models.form_response import FormResponse
from chafan_core.app.models.question import Question
from chafan_core.app.models.reward import Reward
from chafan_core.app.models.submission import Submission
from chafan_core.app.models.submission_suggestion import SubmissionSuggestion
from chafan_core.app.models.task import Task
from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403

followers = Table(
    "followers",
    Base.metadata,
    Column("follower_id", Integer, ForeignKey("user.id"), index=True),
    Column("followed_id", Integer, ForeignKey("user.id"), index=True),
)

subscribed_questions_table = Table(
    "subscribed_questions",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("question_id", Integer, ForeignKey("question.id")),
)

subscribed_submissions_table = Table(
    "subscribed_submission",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("submission_id", Integer, ForeignKey("submission.id")),
)

subscribed_article_columns_table = Table(
    "subscribed_article_columns",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("article_column_id", Integer, ForeignKey("articlecolumn.id")),
)

bookmarked_articles_table = Table(
    "bookmarked_articles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("article_id", Integer, ForeignKey("article.id")),
)

bookmarked_answers_table = Table(
    "bookmarked_answers",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("answer_id", Integer, ForeignKey("answer.id")),
)


subscribed_topics_table = Table(
    "subscribed_topics",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)

residency_topics_table = Table(
    "residency_topics",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)

profession_topics_table = Table(
    "profession_topics",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)


class User(Base):
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = Column(
        CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False
    )
    full_name: Mapped[Optional[str]] = Column(String)
    handle: Mapped[str] = Column(String, unique=True, index=True, nullable=False)
    email: Mapped[str] = Column(String, unique=True, index=True, nullable=False)
    secondary_emails: Mapped[Any] = Column(JSON, server_default="[]", nullable=False)

    phone_number_country_code: Mapped[Optional[str]] = Column(
        String, unique=True, index=True
    )
    phone_number_subscriber_number: Mapped[Optional[str]] = Column(
        String, unique=True, index=True
    )

    hashed_password: Mapped[str] = Column(String, nullable=False)
    is_active: Mapped[bool] = Column(
        Boolean(), server_default="true", nullable=False, default=True
    )
    is_superuser: Mapped[bool] = Column(Boolean(), default=False)
    created_at: Mapped[datetime.datetime] = Column(DateTime(timezone=True), nullable=False)
    verified_telegram_user_id: Mapped[Optional[str]] = Column(String, nullable=True)

    subscribed_article_columns: Mapped[List["ArticleColumn"]] = relationship(
        "ArticleColumn",
        secondary=subscribed_article_columns_table,
        backref=backref("subscribers", lazy="dynamic"),
        lazy="dynamic",
        order_by="ArticleColumn.created_at.desc()",
    )

    bookmarked_articles: Mapped[List["Article"]] = relationship(
        "Article",
        secondary=bookmarked_articles_table,
        backref=backref("bookmarkers", lazy="dynamic"),
        lazy="dynamic",
        order_by="Article.initial_published_at.desc()",
    )

    subscribed_questions: Mapped[List["Question"]] = relationship(
        "Question",
        secondary=subscribed_questions_table,
        backref=backref("subscribers", lazy="dynamic"),
        lazy="dynamic",
        order_by="Question.created_at.desc()",
    )

    subscribed_submissions: Mapped[List["Submission"]] = relationship(
        "Submission",
        secondary=subscribed_submissions_table,
        backref=backref("subscribers", lazy="dynamic"),
        lazy="dynamic",
        order_by="Submission.created_at.desc()",
    )

    bookmarked_answers: Mapped[List["Answer"]] = relationship(
        "Answer",
        secondary=bookmarked_answers_table,
        backref=backref("bookmarkers", lazy="dynamic"),
        lazy="dynamic",
        order_by="Answer.updated_at.desc()",
    )

    subscribed_topics: Mapped[List["Topic"]] = relationship(
        "Topic",
        secondary=subscribed_topics_table,
        backref=backref("subscribers", lazy="dynamic"),
    )

    residency_topics: Mapped[List["Topic"]] = relationship(
        "Topic",
        secondary=residency_topics_table,
        backref=backref("residents", lazy="dynamic"),
    )

    profession_topics: Mapped[List["Topic"]] = relationship(
        "Topic",
        secondary=profession_topics_table,
        backref=backref("professionals", lazy="dynamic"),
    )

    # TODO: deprecate this
    profession_topic_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("topic.id"))

    work_experiences: Mapped[Optional[Any]] = Column(JSON)
    education_experiences: Mapped[Optional[Any]] = Column(JSON)
    personal_introduction: Mapped[Optional[str]] = Column(String)
    about: Mapped[Optional[str]] = Column(String)  # TODO: Add about_text

    # social links
    github_username: Mapped[Optional[str]] = Column(String)
    twitter_username: Mapped[Optional[str]] = Column(String)
    zhihu_url: Mapped[Optional[str]] = Column(String)
    linkedin_url: Mapped[Optional[str]] = Column(String)
    homepage_url: Mapped[Optional[str]] = Column(String)

    followed: Mapped[List["User"]] = relationship(
        "User",
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=backref("followers", lazy="dynamic"),
        lazy="dynamic",
    )

    moderated_sites: Mapped[List["Site"]] = relationship(
        "Site", back_populates="moderator"
    )
    profiles: Mapped[List["Profile"]] = relationship("Profile", back_populates="owner")

    feedbacks: Mapped[List["Feedback"]] = relationship(
        "Feedback",
        back_populates="user",
        order_by="Feedback.created_at.desc()",
        foreign_keys=[Feedback.user_id],
    )
    questions: Mapped[List["Question"]] = relationship(
        "Question",
        back_populates="author",
        order_by="Question.created_at.desc()",
        foreign_keys=[Question.author_id],
    )
    submissions: Mapped[List["Submission"]] = relationship(
        "Submission",
        back_populates="author",
        order_by="Submission.created_at.desc()",
        foreign_keys=[Submission.author_id],
    )
    submission_suggestions: Mapped[List["SubmissionSuggestion"]] = relationship(
        "SubmissionSuggestion",
        back_populates="author",
        order_by="SubmissionSuggestion.created_at.desc()",
        foreign_keys=[SubmissionSuggestion.author_id],
    )
    answer_suggest_edits: Mapped[List["AnswerSuggestEdit"]] = relationship(
        "AnswerSuggestEdit",
        back_populates="author",
        order_by="AnswerSuggestEdit.created_at.desc()",
        foreign_keys=[AnswerSuggestEdit.author_id],
    )
    answers: Mapped[List["Answer"]] = relationship(
        "Answer", back_populates="author", order_by="Answer.updated_at.desc()"
    )
    articles: Mapped[List["Article"]] = relationship(
        "Article", back_populates="author", order_by="Article.updated_at.desc()"
    )
    applications: Mapped[List["Application"]] = relationship(
        "Application",
        back_populates="applicant",
        order_by="Application.created_at.desc()",
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        order_by="AuditLog.created_at.desc()",
    )
    initiated_tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="initiator",
        order_by="Task.created_at.desc()",
    )
    article_columns: Mapped[List["ArticleColumn"]] = relationship(
        "ArticleColumn",
        back_populates="owner",
        order_by="ArticleColumn.created_at.desc()",
    )
    comments: Mapped[List["Comment"]] = relationship(
        "Comment", back_populates="author", order_by="Comment.updated_at.desc()"
    )
    authored_reports: Mapped[List["Report"]] = relationship(
        "Report", back_populates="author", order_by="Report.created_at.desc()"
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="author", order_by="Message.updated_at.desc()"
    )
    forms: Mapped[List["Form"]] = relationship(
        "Form", back_populates="author", order_by="Form.created_at.desc()"
    )
    form_responses: Mapped[List["FormResponse"]] = relationship(
        "FormResponse",
        back_populates="response_author",
        order_by="FormResponse.created_at.desc()",
        foreign_keys=[FormResponse.response_author_id],
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="receiver",
        order_by="Notification.created_at.desc()",
    )

    outgoing_rewards: Mapped[List["Reward"]] = relationship(
        "Reward",
        back_populates="giver",
        foreign_keys=[Reward.giver_id],
        order_by="Reward.created_at.asc()",
    )
    incoming_rewards: Mapped[List["Reward"]] = relationship(
        "Reward",
        back_populates="receiver",
        foreign_keys=[Reward.receiver_id],
        order_by="Reward.created_at.asc()",
    )

    out_coin_payments: Mapped[List["CoinPayment"]] = relationship(
        "CoinPayment", back_populates="payer", foreign_keys=[CoinPayment.payer_id]
    )
    in_coin_payments: Mapped[List["CoinPayment"]] = relationship(
        "CoinPayment", back_populates="payee", foreign_keys=[CoinPayment.payee_id]
    )
    in_coin_deposits: Mapped[List["CoinDeposit"]] = relationship(
        "CoinDeposit", back_populates="payee", foreign_keys=[CoinDeposit.payee_id]
    )
    authorized_deposits: Mapped[List["CoinDeposit"]] = relationship(
        "CoinDeposit",
        back_populates="authorizer",
        foreign_keys=[CoinDeposit.authorizer_id],
    )
    remaining_coins: Mapped[int] = Column(
        Integer, server_default="0", default=0, nullable=False
    )

    # Behavior information
    sent_new_user_invitataions: Mapped[int] = Column(
        Integer, server_default="0", nullable=False, default=0
    )
    flags: Mapped[Optional[str]] = Column(String)

    avatar_url: Mapped[Optional[str]] = Column(String)
    gif_avatar_url: Mapped[Optional[str]] = Column(String)

    unsubscribe_token: Mapped[Optional[str]] = Column(String)

    karma: Mapped[int] = Column(Integer, nullable=False, server_default="0")

    claimed_welcome_test_rewards_with_form_response_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("formresponse.id"), nullable=True
    )

    # functionality preferences
    enable_deliver_unread_notifications: Mapped[bool] = Column(
        Boolean(), server_default="true", nullable=False, default=True
    )
    default_editor_mode: Mapped[str] = Column(
        String, nullable=False, server_default="wysiwyg"
    )
    locale_preference: Mapped[Optional[str]] = Column(String)

    feed_settings: Mapped[Optional[Any]] = Column(JSON, nullable=True)

    ######### Derived fields #########
    keywords: Mapped[Optional[Any]] = Column(JSON, nullable=True)

    # top-N interesting questions
    interesting_question_ids: Mapped[Optional[Any]] = Column(JSON, nullable=True)
    interesting_question_ids_updated_at: Mapped[Optional[datetime.datetime]] = Column(
        DateTime(timezone=True), nullable=True
    )

    # top-N interesting users
    interesting_user_ids: Mapped[Optional[Any]] = Column(JSON, nullable=True)
    interesting_user_ids_updated_at: Mapped[Optional[datetime.datetime]] = Column(
        DateTime(timezone=True), nullable=True
    )
