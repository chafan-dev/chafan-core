
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    Table,
    UniqueConstraint,
)

from chafan_core.db.base_class import Base


#if TYPE_CHECKING:
#    from . import *  # noqa: F401, F403

class ViewCountArticle(Base):
    __table_args__ = (
        UniqueConstraint("article_id"),
        PrimaryKeyConstraint("article_id"),
    )
    article_id = Column(Integer, ForeignKey("article.id"), nullable=False, index=True)
    view_count = Column(Integer, default=0, server_default="0", nullable=False)

class ViewCountQuestion(Base):
    __table_args__ = (
        UniqueConstraint("question_id"),
        PrimaryKeyConstraint("question_id"),
    )
    question_id = Column(Integer, ForeignKey("question.id"), nullable=True, index=True)
    view_count = Column(Integer, default=0, server_default="0", nullable=False)

class ViewCountAnswer(Base):
    __table_args__ = (
        UniqueConstraint("answer_id"),
        PrimaryKeyConstraint("answer_id"),
    )
    answer_id = Column(Integer, ForeignKey("answer.id"), nullable=True, index=True)
    view_count = Column(Integer, default=0, server_default="0", nullable=False)

class ViewCountSubmission(Base):
    __table_args__ = (
        UniqueConstraint("submission_id"),
        PrimaryKeyConstraint("submission_id"),
    )
    submission_id = Column(Integer, ForeignKey("submission.id"), nullable=True, index=True)
    view_count = Column(Integer, default=0, server_default="0", nullable=False)
