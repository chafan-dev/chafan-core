from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class FormResponse(Base):
    id = Column(Integer, primary_key=True, index=True)
    response_author_id = Column(
        Integer, ForeignKey("user.id"), nullable=False, index=True
    )
    response_author = relationship(
        "User", back_populates="form_responses", foreign_keys=[response_author_id]
    )
    form_id = Column(Integer, ForeignKey("form.id"), nullable=False, index=True)
    form: "Form" = relationship("Form", back_populates="responses")  # type: ignore

    created_at = Column(DateTime(timezone=True), nullable=False)

    response_fields = Column(JSON, nullable=False)
