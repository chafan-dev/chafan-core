from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from chafan_core.db.base_class import Base
from chafan_core.utils.base import ReportReason

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Report(Base):
    id = Column(Integer, primary_key=True, index=True)

    author_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    author = relationship("User", back_populates="authored_reports")

    question_id = Column(Integer, ForeignKey("question.id"), index=True)
    question: Optional["Question"] = relationship("Question", back_populates="reports")  # type: ignore

    submission_id = Column(Integer, ForeignKey("submission.id"), index=True)
    submission: Optional["Submission"] = relationship("Submission", back_populates="reports")  # type: ignore

    article_id = Column(Integer, ForeignKey("article.id"), index=True)
    article: Optional["Article"] = relationship("Article", back_populates="reports")  # type: ignore

    answer_id = Column(Integer, ForeignKey("answer.id"), index=True)
    answer: Optional["Answer"] = relationship("Answer", back_populates="reports")  # type: ignore

    comment_id = Column(Integer, ForeignKey("comment.id"), index=True)
    comment: Optional["Comment"] = relationship("Comment", back_populates="reports")  # type: ignore

    created_at = Column(DateTime(timezone=True), nullable=False)

    reason: ReportReason = Column(Enum(ReportReason), nullable=False, index=True)
    reason_comment = Column(String, nullable=True)
