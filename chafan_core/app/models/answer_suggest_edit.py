from typing import TYPE_CHECKING, Optional

from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH
from chafan_core.utils.constants import editor_T

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class AnswerSuggestEdit(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)

    author_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    author: "User" = relationship(
        "User", back_populates="answer_suggest_edits", foreign_keys=[author_id]
    )  # type: ignore

    # RichText content
    body = Column(String)
    body_text = Column(String)
    body_editor: Optional[editor_T] = Column(String)

    created_at = Column(DateTime(timezone=True), nullable=False)

    comment = Column(String)

    status = Column(String, nullable=False, default="pending")
    accepted_at = Column(DateTime(timezone=True))
    rejected_at = Column(DateTime(timezone=True))
    retracted_at = Column(DateTime(timezone=True))
    accepted_diff_base = Column(JSON)  # None when not accepted yet

    answer_id = Column(Integer, ForeignKey("answer.id"), nullable=False, index=True)
    answer: "Answer" = relationship("Answer", back_populates="suggest_edits", foreign_keys=[answer_id])  # type: ignore
