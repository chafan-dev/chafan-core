
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
)

from chafan_core.db.base_class import Base


#if TYPE_CHECKING:
#    from . import *  # noqa: F401, F403

# One row per content item, keyed by the content it counts.
#
# The primary key already supplies both NOT NULL and uniqueness, so these
# columns are nullable=False and carry no separate UniqueConstraint. Declaring
# either made the model disagree with a database that was in fact correct:
# Postgres forces a PK column NOT NULL whatever the model says, and a
# UniqueConstraint duplicating the PK is never materialized. `alembic check`
# reported that disagreement as permanent drift.

class ViewCountArticle(Base):
    __table_args__ = (
        PrimaryKeyConstraint("article_id"),
    )
    article_id = Column(Integer, ForeignKey("article.id"), nullable=False, index=True)
    view_count = Column(Integer, default=0, server_default="0", nullable=False)

class ViewCountQuestion(Base):
    __table_args__ = (
        PrimaryKeyConstraint("question_id"),
    )
    question_id = Column(Integer, ForeignKey("question.id"), nullable=False, index=True)
    view_count = Column(Integer, default=0, server_default="0", nullable=False)

class ViewCountAnswer(Base):
    __table_args__ = (
        PrimaryKeyConstraint("answer_id"),
    )
    answer_id = Column(Integer, ForeignKey("answer.id"), nullable=False, index=True)
    view_count = Column(Integer, default=0, server_default="0", nullable=False)

class ViewCountSubmission(Base):
    __table_args__ = (
        PrimaryKeyConstraint("submission_id"),
    )
    submission_id = Column(Integer, ForeignKey("submission.id"), nullable=False, index=True)
    view_count = Column(Integer, default=0, server_default="0", nullable=False)
