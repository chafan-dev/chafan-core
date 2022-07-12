from typing import TYPE_CHECKING, List

from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.db.base_class import Base
from chafan_core.utils.base import UUID_LENGTH

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class ArticleColumn(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(length=UUID_LENGTH), index=True, unique=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    owner = relationship(
        "User", back_populates="article_columns", foreign_keys=[owner_id]
    )
    name = Column(String, nullable=False)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), nullable=False)

    articles: List["Article"] = relationship(  # type: ignore
        "Article", back_populates="article_column", order_by="Article.created_at.desc()"
    )

    keywords = Column(JSON)
