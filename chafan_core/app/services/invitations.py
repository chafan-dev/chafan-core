"""Invitation link domain service."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.infra import cache as infra_cache
from chafan_core.app.responders import misc as misc_responder
from chafan_core.app.schemas.invitation_link import InvitationLinkCreate
from chafan_core.app.services import sites as sites_service
from chafan_core.app.user_permission import check_user_in_site
from chafan_core.utils.base import HTTPException_, unwrap

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
    # TODO we didn't check if this user is allowed to invite new users 2025-Jul-06
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
    invitation_link = crud.invitation_link.get_by_uuid(db, uuid=uuid)
    if invitation_link is None or not invitation_link_schema(ctx, invitation_link).valid:
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
        invitation_link.remaining_quota -= 1
        db.add(invitation_link)
        db.commit()
