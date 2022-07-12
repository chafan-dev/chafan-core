from typing import TYPE_CHECKING, List

from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Form(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)
    author_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    author = relationship("User", back_populates="forms")

    title = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    form_fields = Column(JSON, nullable=False)

    responses: List["FormResponse"] = relationship(  # type: ignore
        "FormResponse", back_populates="form", order_by="FormResponse.created_at.desc()"
    )
