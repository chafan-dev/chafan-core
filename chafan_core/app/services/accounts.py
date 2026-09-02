"""Account creation and the coin reward paid for a successful invitation.

Distinct from `services/auth.py` (which authenticates an existing account) and
from `services/invitations.py` (which owns invitation *links*).
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from fastapi import status
from pydantic.types import SecretStr
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, rules, schemas
from chafan_core.app.common import check_email
from chafan_core.app.config import settings
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.responders.user import user_schema_from_orm
from chafan_core.app.schemas.event import EventInternal, InviteNewUserInternal
from chafan_core.app.security import check_digit_verification_code
from chafan_core.app.services import invitations as invitations_service
from chafan_core.utils.base import HTTPException_
from chafan_core.utils.validators import (
    CaseInsensitiveEmailStr,
    StrippedNonEmptyBasicStr,
    check_password,
)

logger = logging.getLogger(__name__)


def open_account(
    ctx: RequestContext,
    *,
    email: CaseInsensitiveEmailStr,
    handle: StrippedNonEmptyBasicStr,
    password: SecretStr,
    code: str,
    invitation_link_uuid: str,
) -> schemas.User:
    if not settings.USERS_OPEN_REGISTRATION:
        raise HTTPException_(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Open user registration is forbidden on this server",
        )
    check_email(email)
    check_password(password)

    db = ctx.get_db()

    # TODO audit log should support user_id is NULL. 2025-Jul-06
    crud.audit_log.create_with_user(
        db, ipaddr="0.0.0.0", user_id=1, api="Open new account email " + email
    )
    invitation_link = invitations_service.resolve_usable_invitation_link(
        db, invitation_link_uuid
    )
    if invitation_link is None:
        raise HTTPException_(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid invitation link",
        )

    user = crud.user.get_by_email(db, email=email)
    if user:
        raise HTTPException_(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The user with this email already exists in the system",
        )
    user = crud.user.get_by_handle(db, handle=handle)
    if user:
        raise HTTPException_(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The user with this username already exists in the system",
        )
    logger.info(f"No existing user info found for email={email}, handle={handle}")

    ver_code = check_digit_verification_code(email, code)
    if not ver_code:
        raise HTTPException_(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The verification code is not present in the system.",
        )
    user_in = schemas.UserCreate(password=password, handle=handle, email=email)
    user = crud.user.create(db, obj_in=user_in)

    # Only now, with the account actually created, does the invitation cost
    # the inviter a slot and earn them the reward. Everything above this line
    # can still reject the signup, and a rejected signup must be free.
    invitations_service.consume(db, invitation_link)
    pay_reward_for_invitation(
        db,
        inviter=invitation_link.inviter,
        invited_to_site_id=invitation_link.invited_to_site_id,
        invited_email=email,
    )
    return user_schema_from_orm(user)


def pay_reward_for_invitation(
    db: Session,
    *,
    inviter: models.User,
    invited_to_site_id: Optional[int],
    invited_email: Optional[CaseInsensitiveEmailStr],
) -> Optional[int]:
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    superuser = crud.user.get_superuser(db)
    if inviter.id == superuser.id:
        # The admin funds this reward, so there is no one to pay when the admin
        # is also the inviter -- as with the shared daily link.
        return None
    invitations_sent = inviter.sent_new_user_invitataions
    # Counts every invitation that brought someone in, rewarded or not, so that
    # a spell of the admin being broke cannot hand anyone extra rewarded slots.
    inviter.sent_new_user_invitataions = invitations_sent + 1
    db.add(inviter)
    if (
        invitations_sent < rules.INVITE_NEW_USER_MAX_REWARDED
        and superuser.remaining_coins >= rules.INVITE_NEW_USER_REWARD
    ):
        crud.coin_payment.make_payment(
            db,
            obj_in=schemas.CoinPaymentCreate(
                payee_id=inviter.id,
                amount=rules.INVITE_NEW_USER_REWARD,
                event_json=EventInternal(
                    created_at=utc_now,
                    content=InviteNewUserInternal(
                        subject_id=inviter.id,
                        site_id=invited_to_site_id,
                        invited_email=invited_email,
                    ),
                ).json(),
            ),
            payer=superuser,
            payee=inviter,
        )
        return rules.INVITE_NEW_USER_REWARD
    return None
