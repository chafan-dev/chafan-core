"""Invitation link domain service."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.infra import cache as infra_cache
from chafan_core.app.materialize import Materializer
from chafan_core.utils.base import unwrap

logger = logging.getLogger(__name__)


def try_consume_invitation_link_by_uuid(db: Session, invitation_uuid: str) -> bool:
    logger.info(f"Consumed invitation link uuid=${invitation_uuid}")
    invitation_link = crud.invitation_link.get_by_uuid(db, uuid=invitation_uuid)
    if invitation_link is None:
        logger.info(f"Invalid invitation uuid=${invitation_uuid}")
        return False
    if invitation_link.remaining_quota < 1:
        logger.info(f"Invitation quota has exceeded limit uuid=${invitation_uuid}")
        return False
    invitation_link.remaining_quota -= 1
    db.add(invitation_link)
    db.commit()
    return True


def get_daily_invitation_link(db: Session, materializer: Materializer) -> schemas.InvitationLink:
    def fetch() -> int:
        return crud.invitation_link.create_invitation(
            db, invited_to_site_id=None, inviter=crud.user.get_superuser(db)
        ).id

    cached_id = infra_cache.get_or_set(
        key=infra_cache.DAILY_INVITATION_LINK_ID_CACHE_KEY,
        type_=int,
        fetch=fetch,
        ttl_hours=24,
    )
    return materializer.invitation_link_schema_from_orm(
        unwrap(crud.invitation_link.get(db, id=cached_id))
    )
