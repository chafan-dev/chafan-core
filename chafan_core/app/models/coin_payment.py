from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import UniqueConstraint

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class CoinPayment(Base):
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Integer, nullable=False)
    event_json = Column(String)  # Change to nullable=False after deprecation of ref_id
    payer_id = Column("payer_id", Integer, ForeignKey("user.id"), nullable=False)
    payer = relationship(
        "User", back_populates="out_coin_payments", foreign_keys=[payer_id]
    )
    payee_id = Column("payee_id", Integer, ForeignKey("user.id"), nullable=False)
    payee = relationship(
        "User", back_populates="in_coin_payments", foreign_keys=[payee_id]
    )
    comment = Column(String)

    __table_args__ = (UniqueConstraint("event_json", "payee_id", "payer_id"),)
