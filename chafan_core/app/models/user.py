from typing import TYPE_CHECKING, List, Literal, Optional

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
from sqlalchemy.orm import backref, relationship
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
from chafan_core.utils.validators import StrippedNonEmptyBasicStr

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
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)
    full_name = Column(String)
    handle: "StrippedNonEmptyBasicStr" = Column(
        String, unique=True, index=True, nullable=False
    )
    email = Column(String, unique=True, index=True, nullable=False)
    secondary_emails = Column(JSON, server_default="[]", nullable=False)

    phone_number_country_code = Column(String, unique=True, index=True)
    phone_number_subscriber_number = Column(String, unique=True, index=True)

    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), server_default="true", nullable=False, default=True)
    is_superuser = Column(Boolean(), default=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    verified_telegram_user_id = Column(String, nullable=True)

    subscribed_article_columns: List["ArticleColumn"] = relationship(  # type: ignore
        "ArticleColumn",
        secondary=subscribed_article_columns_table,
        backref=backref("subscribers", lazy="dynamic"),
        lazy="dynamic",
        order_by="ArticleColumn.created_at.desc()",
    )

    bookmarked_articles: List["Article"] = relationship(  # type: ignore
        "Article",
        secondary=bookmarked_articles_table,
        backref=backref("bookmarkers", lazy="dynamic"),
        lazy="dynamic",
        order_by="Article.initial_published_at.desc()",
    )

    subscribed_questions: List["Question"] = relationship(  # type: ignore
        "Question",
        secondary=subscribed_questions_table,
        backref=backref("subscribers", lazy="dynamic"),
        lazy="dynamic",
        order_by="Question.created_at.desc()",
    )

    subscribed_submissions: List["Submission"] = relationship(  # type: ignore
        "Submission",
        secondary=subscribed_submissions_table,
        backref=backref("subscribers", lazy="dynamic"),
        lazy="dynamic",
        order_by="Submission.created_at.desc()",
    )

    bookmarked_answers: List["Answer"] = relationship(  # type: ignore
        "Answer",
        secondary=bookmarked_answers_table,
        backref=backref("bookmarkers", lazy="dynamic"),
        lazy="dynamic",
        order_by="Answer.updated_at.desc()",
    )

    subscribed_topics: List["Topic"] = relationship(  # type: ignore
        "Topic",
        secondary=subscribed_topics_table,
        backref=backref("subscribers", lazy="dynamic"),
    )

    residency_topics: List["Topic"] = relationship(  # type: ignore
        "Topic",
        secondary=residency_topics_table,
        backref=backref("residents", lazy="dynamic"),
    )

    profession_topics: List["Topic"] = relationship(  # type: ignore
        "Topic",
        secondary=profession_topics_table,
        backref=backref("professionals", lazy="dynamic"),
    )

    # TODO: deprecate this
    profession_topic_id = Column(Integer, ForeignKey("topic.id"))

    work_experiences = Column(JSON)
    education_experiences = Column(JSON)
    personal_introduction = Column(String)
    about = Column(String)  # TODO: Add about_text

    # social links
    github_username = Column(String)
    twitter_username = Column(String)
    zhihu_url: Optional[AnyHttpUrl] = Column(String)  # type: ignore
    linkedin_url: Optional[AnyHttpUrl] = Column(String)  # type: ignore
    homepage_url: Optional[AnyHttpUrl] = Column(String)  # type: ignore

    followed: List["User"] = relationship(  # type: ignore
        "User",
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=backref("followers", lazy="dynamic"),
        lazy="dynamic",
    )

    moderated_sites: List["Site"] = relationship("Site", back_populates="moderator")  # type: ignore
    profiles: List["Profile"] = relationship("Profile", back_populates="owner")  # type: ignore

    feedbacks: List["Feedback"] = relationship(  # type: ignore
        "Feedback",
        back_populates="user",
        order_by="Feedback.created_at.desc()",
        foreign_keys=[Feedback.user_id],
    )
    questions: List["Question"] = relationship(  # type: ignore
        "Question",
        back_populates="author",
        order_by="Question.created_at.desc()",
        foreign_keys=[Question.author_id],
    )
    submissions: List["Submission"] = relationship(  # type: ignore
        "Submission",
        back_populates="author",
        order_by="Submission.created_at.desc()",
        foreign_keys=[Submission.author_id],
    )
    submission_suggestions: List["SubmissionSuggestion"] = relationship(  # type: ignore
        "SubmissionSuggestion",
        back_populates="author",
        order_by="SubmissionSuggestion.created_at.desc()",
        foreign_keys=[SubmissionSuggestion.author_id],
    )
    answer_suggest_edits: List["AnswerSuggestEdit"] = relationship(  # type: ignore
        "AnswerSuggestEdit",
        back_populates="author",
        order_by="AnswerSuggestEdit.created_at.desc()",
        foreign_keys=[AnswerSuggestEdit.author_id],
    )
    answers: List["Answer"] = relationship(  # type: ignore
        "Answer", back_populates="author", order_by="Answer.updated_at.desc()"
    )
    articles: List["Article"] = relationship(  # type: ignore
        "Article", back_populates="author", order_by="Article.updated_at.desc()"
    )
    applications: List["Application"] = relationship(  # type: ignore
        "Application",
        back_populates="applicant",
        order_by="Application.created_at.desc()",
    )
    audit_logs: List["AuditLog"] = relationship(  # type: ignore
        "AuditLog",
        back_populates="user",
        order_by="AuditLog.created_at.desc()",
    )
    initiated_tasks: List["Task"] = relationship(  # type: ignore
        "Task",
        back_populates="initiator",
        order_by="Task.created_at.desc()",
    )
    article_columns: List["ArticleColumn"] = relationship(  # type: ignore
        "ArticleColumn",
        back_populates="owner",
        order_by="ArticleColumn.created_at.desc()",
    )
    comments: List["Comment"] = relationship(  # type: ignore
        "Comment", back_populates="author", order_by="Comment.updated_at.desc()"
    )
    authored_reports: List["Report"] = relationship(  # type: ignore
        "Report", back_populates="author", order_by="Report.created_at.desc()"
    )
    messages: List["Message"] = relationship(  # type: ignore
        "Message", back_populates="author", order_by="Message.updated_at.desc()"
    )
    forms: List["Form"] = relationship(  # type: ignore
        "Form", back_populates="author", order_by="Form.created_at.desc()"
    )
    form_responses: List["FormResponse"] = relationship(  # type: ignore
        "FormResponse",
        back_populates="response_author",
        order_by="FormResponse.created_at.desc()",
        foreign_keys=[FormResponse.response_author_id],
    )
    notifications: List["Notification"] = relationship(  # type: ignore
        "Notification",
        back_populates="receiver",
        order_by="Notification.created_at.desc()",
    )

    outgoing_rewards: List["Reward"] = relationship(  # type: ignore
        "Reward",
        back_populates="giver",
        foreign_keys=[Reward.giver_id],
        order_by="Reward.created_at.asc()",
    )
    incoming_rewards: List["Reward"] = relationship(  # type: ignore
        "Reward",
        back_populates="receiver",
        foreign_keys=[Reward.receiver_id],
        order_by="Reward.created_at.asc()",
    )

    out_coin_payments: List["CoinPayment"] = relationship(  # type: ignore
        "CoinPayment", back_populates="payer", foreign_keys=[CoinPayment.payer_id]
    )
    in_coin_payments: List["CoinPayment"] = relationship(  # type: ignore
        "CoinPayment", back_populates="payee", foreign_keys=[CoinPayment.payee_id]
    )
    in_coin_deposits: List["CoinDeposit"] = relationship(  # type: ignore
        "CoinDeposit", back_populates="payee", foreign_keys=[CoinDeposit.payee_id]
    )
    authorized_deposits: List["CoinDeposit"] = relationship(  # type: ignore
        "CoinDeposit",
        back_populates="authorizer",
        foreign_keys=[CoinDeposit.authorizer_id],
    )
    remaining_coins = Column(Integer, server_default="0", default=0, nullable=False)

    # Behavior information
    sent_new_user_invitataions = Column(
        Integer, server_default="0", nullable=False, default=0
    )
    flags = Column(String)

    avatar_url = Column(String)
    gif_avatar_url: Optional[AnyHttpUrl] = Column(String)  # type: ignore

    unsubscribe_token = Column(String)

    karma = Column(Integer, nullable=False, server_default="0")

    claimed_welcome_test_rewards_with_form_response_id = Column(
        Integer, ForeignKey("formresponse.id"), nullable=True
    )

    # functionality preferences
    enable_deliver_unread_notifications = Column(
        Boolean(), server_default="true", nullable=False, default=True
    )
    default_editor_mode = Column(String, nullable=False, server_default="wysiwyg")
    locale_preference: Optional[Literal["en", "zh"]] = Column(String)  # type: ignore

    feed_settings = Column(JSON, nullable=True)

    keywords: Optional[List[str]] = Column(JSON)  # type: ignore
