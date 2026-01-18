from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, relationship

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Profile(Base):
    __table_args__ = (
        UniqueConstraint("owner_id", "site_id"),
        PrimaryKeyConstraint("owner_id", "site_id"),
    )

    karma: Mapped[int] = Column(Integer, nullable=False, server_default="0")
    owner_id: Mapped[int] = Column(Integer, ForeignKey("user.id"), primary_key=True)
    owner: Mapped["User"] = relationship("User", back_populates="profiles")
    site_id: Mapped[int] = Column(
        Integer, ForeignKey("site.id"), primary_key=True, nullable=False
    )
    site: Mapped["Site"] = relationship("Site", back_populates="profiles")
