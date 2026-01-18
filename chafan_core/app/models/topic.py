from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import CHAR, Column, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.sql.sqltypes import Boolean

from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Topic(Base):
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = Column(
        CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False
    )
    name: Mapped[str] = Column(String, nullable=False)
    description: Mapped[Optional[str]] = Column(String)
    is_category: Mapped[Optional[bool]] = Column(Boolean, server_default="false")

    parent_topic_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("topic.id"), index=True
    )
    parent_topic: Mapped[Optional["Topic"]] = relationship(
        "Topic", back_populates="child_topics", remote_side=[id]
    )

    child_topics: Mapped[List["Topic"]] = relationship(
        "Topic", back_populates="parent_topic"
    )
