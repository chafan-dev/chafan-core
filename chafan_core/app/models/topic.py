from typing import TYPE_CHECKING, List

from sqlalchemy import CHAR, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import Boolean

from chafan_core.utils.base import UUID_LENGTH
from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Topic(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)
    is_category = Column(Boolean, server_default="false")

    parent_topic_id = Column(Integer, ForeignKey("topic.id"), index=True)
    parent_topic = relationship(
        "Topic", back_populates="child_topics", remote_side=[id]
    )

    child_topics: List["Topic"] = relationship("Topic", back_populates="parent_topic")  # type: ignore
