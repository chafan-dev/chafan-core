"""User invite domain service."""

from __future__ import annotations

import datetime

from chafan_core.app import crud, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.schemas.event import EventInternal, InviteJoinSiteInternal
from chafan_core.app.services import sites as sites_service
from chafan_core.app.user_permission import check_user_in_site
from chafan_core.utils.base import HTTPException_


def invite_user_to_site(ctx, *, user_invite_in: schemas.UserInvite) -> None:
    db = ctx.get_db()
    site = get_site(db, user_invite_in.site_uuid)
    check_user_in_site(
        db,
        site=site,
        user_id=ctx.unwrapped_principal_id(),
        op_type=OperationType.AddSiteMember,
    )
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    assert user_invite_in.user_uuid is not None
    invited_user = crud.user.get_by_uuid(db, uuid=user_invite_in.user_uuid)
    if not invited_user:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exist.",
        )
    existing_profile = crud.profile.get_by_user_and_site(
        db, owner_id=invited_user.id, site_id=site.id
    )
    if not existing_profile:
        sites_service.create_site_profile(
            db,
            ctx.principal_view,
            owner=invited_user,
            site_uuid=site.uuid,
        )
        application = crud.application.get_by_applicant_and_site(
            db, applicant=invited_user, site=site
        )
        if application is not None:
            crud.application.update(
                db,
                db_obj=application,
                obj_in=schemas.ApplicationUpdate(pending=False),
            )
        crud.notification.create_with_content(
            ctx,
            receiver_id=invited_user.id,
            event=EventInternal(
                created_at=utc_now,
                content=InviteJoinSiteInternal(
                    subject_id=ctx.unwrapped_principal_id(),
                    site_id=site.id,
                    user_id=invited_user.id,
                ),
            ),
        )
