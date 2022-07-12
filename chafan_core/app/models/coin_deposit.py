from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class CoinDeposit(Base):
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Integer, nullable=False)
    ref_id = Column(String, nullable=False, unique=True)
    authorizer_id = Column("authorizer_id", Integer, ForeignKey("user.id"))
    authorizer = relationship(
        "User", back_populates="authorized_deposits", foreign_keys=[authorizer_id]
    )
    payee_id = Column("payee_id", Integer, ForeignKey("user.id"))
    payee = relationship(
        "User", back_populates="in_coin_deposits", foreign_keys=[payee_id]
    )
    comment = Column(String)
