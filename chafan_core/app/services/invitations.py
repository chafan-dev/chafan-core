"""Invitation link domain service."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models, rules, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.infra import cache as infra_cache
from chafan_core.app.model_utils import is_usable_invitation_link
from chafan_core.app.responders import misc as misc_responder
from chafan_core.app.schemas.invitation_link import InvitationLinkCreate
from chafan_core.app.services import sites as sites_service
from chafan_core.app.user_permission import check_user_in_site
from chafan_core.utils.base import HTTPException_, unwrap

logger = logging.getLogger(__name__)


def resolve_usable_invitation_link(
    db: Session, invitation_uuid: str
) -> Optional[models.InvitationLink]:
    """The link `invitation_uuid` names, if it can still bring someone in.

    Read-only on purpose: the caller checks the link up front but only spends
    it once whatever it was gating has actually succeeded. See `consume()`.
    """
    invitation_link = crud.invitation_link.get_by_uuid(db, uuid=invitation_uuid)
    if invitation_link is None:
        logger.info(f"Invalid invitation uuid=${invitation_uuid}")
        return None
    if not is_usable_invitation_link(invitation_link):
        logger.info(f"Invitation link is spent or expired uuid=${invitation_uuid}")
        return None
    return invitation_link


def consume(db: Session, invitation_link: models.InvitationLink) -> None:
    """Spend one use of `invitation_link`.

    Call this only once the thing the link was gating has succeeded -- a
    signup that fails validation must not cost the inviter a slot.
    """
    invitation_link.remaining_quota -= 1
    db.add(invitation_link)
    logger.info(
        f"Consumed invitation link uuid=${invitation_link.uuid} "
        f"remaining_quota={invitation_link.remaining_quota}"
    )


def invitation_link_schema(ctx, invitation_link: models.InvitationLink) -> schemas.InvitationLink:
    return misc_responder.invitation_link_schema_from_orm(
        ctx.principal_view, invitation_link
    )


def get_daily_invitation_link(ctx) -> schemas.InvitationLink:
    db = ctx.get_db()

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
    return invitation_link_schema(
        ctx, unwrap(crud.invitation_link.get(db, id=cached_id))
    )


def get_invitation_link(ctx, uuid: str) -> schemas.InvitationLink:
    invitation_link = crud.invitation_link.get_by_uuid(ctx.get_db(), uuid=uuid)
    if invitation_link is None:
        raise HTTPException_(
            status_code=404,
            detail="Invalid invitation link",
        )
    return invitation_link_schema(ctx, invitation_link)


def create_invitation_link(ctx, *, create_in: InvitationLinkCreate) -> schemas.InvitationLink:
    current_user = ctx.get_current_active_user()
    if (
        not current_user.is_superuser
        and (current_user.karma or 0) < rules.MIN_KARMA_INVITE_USER
    ):
        raise HTTPException_(
            status_code=403,
            detail=f"Inviting a new user requires {rules.MIN_KARMA_INVITE_USER} karma.",
        )
    invited_to_site_id = None
    db = ctx.get_db()

    if create_in.invited_to_site_uuid is not None:
        invited_to_site = get_site(db, create_in.invited_to_site_uuid)
        check_user_in_site(
            db,
            site=invited_to_site,
            user_id=current_user.id,
            op_type=OperationType.AddSiteMember,
        )
        invited_to_site_id = invited_to_site.id
    invitation_link = crud.invitation_link.create_invitation(
        db, invited_to_site_id=invited_to_site_id, inviter=current_user
    )
    crud.audit_log.create_with_user(
        db,
        ipaddr="0.0.0.0",
        user_id=current_user.id,
        api=f"Created invitation link {invitation_link.uuid}",
    )
    return invitation_link_schema(ctx, invitation_link)


def join_site_with_invitation_link(ctx, *, uuid: str) -> None:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    invitation_link = resolve_usable_invitation_link(db, uuid)
    if invitation_link is None:
        raise HTTPException_(
            status_code=400,
            detail="Invalid invitation link",
        )
    if invitation_link.invited_to_site_id is None:
        raise HTTPException_(
            status_code=400,
            detail="Not for a specific site",
        )
    existing_profile = crud.profile.get_by_user_and_site(
        db, owner_id=current_user.id, site_id=invitation_link.invited_to_site_id
    )
    if not existing_profile:
        sites_service.create_site_profile(
            db,
            ctx.principal_view,
            owner=current_user,
            site_uuid=invitation_link.invited_to_site.uuid,
        )
        consume(db, invitation_link)
