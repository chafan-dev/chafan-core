from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import JSON

from chafan_core.db.base_class import Base

if TYPE_CHECKING:
    from . import *  # noqa: F401, F403


class Reward(Base):
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    expired_at = Column(DateTime(timezone=True), nullable=False)
    claimed_at = Column(DateTime(timezone=True))
    refunded_at = Column(DateTime(timezone=True))

    giver_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    giver = relationship(
        "User", back_populates="outgoing_rewards", foreign_keys=[giver_id]
    )

    receiver_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    receiver = relationship(
        "User", back_populates="incoming_rewards", foreign_keys=[receiver_id]
    )

    coin_amount = Column(Integer, nullable=False)
    note_to_receiver = Column(String)

    condition = Column(JSON)
