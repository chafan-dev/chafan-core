from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from chafan_core.utils.constants import editor_T
from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class ArticleArchive(Base):
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    body = Column(String, nullable=False)
    editor: editor_T = Column(String, nullable=False, server_default="wysiwyg")  # type: ignore
    created_at = Column(DateTime(timezone=True), nullable=False)
    article_id = Column(Integer, ForeignKey("article.id"), nullable=False, index=True)
    article = relationship("Article", back_populates="archives")
