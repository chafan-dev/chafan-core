from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Profile(Base):
    __table_args__ = (
        UniqueConstraint("owner_id", "site_id"),
        PrimaryKeyConstraint("owner_id", "site_id"),
    )

    karma = Column(Integer, nullable=False, server_default="0")
    owner_id = Column(Integer, ForeignKey("user.id"), primary_key=True)
    owner = relationship("User", back_populates="profiles")
    site_id = Column(Integer, ForeignKey("site.id"), primary_key=True, nullable=False)
    site: "Site" = relationship("Site", back_populates="profiles")  # type: ignore
