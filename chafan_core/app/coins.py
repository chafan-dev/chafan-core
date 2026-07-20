"""Coin balance mutations (shared by crud write helpers and services.reputation).

Kept outside services/ so crud can call it without an upward import.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from chafan_core.app import models

logger = logging.getLogger(__name__)


def deduct_coins(db: Session, user: models.User, amount: int, reason: str) -> None:
    user.remaining_coins -= amount
    db.add(user)
    logger.info(f"deduct_coins user_id={user.id} amount={amount} reason={reason}")


def award_coins(db: Session, user: models.User, amount: int, reason: str) -> None:
    user.remaining_coins += amount
    db.add(user)
    logger.info(f"award_coins user_id={user.id} amount={amount} reason={reason}")
