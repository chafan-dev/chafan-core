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

from chafan_core.app import crud, models, schemas
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
    invitation_link_valid = invitations_service.try_consume_invitation_link_by_uuid(
        db, invitation_link_uuid
    )
    if not invitation_link_valid:
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

    # TODO bonus for invite new user, new user's initial coins
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
    if (
        inviter.sent_new_user_invitataions < 10
        and superuser.remaining_coins >= settings.INVITE_NEW_USER_COIN_PAYMENT_AMOUNT
    ):
        crud.coin_payment.make_payment(
            db,
            obj_in=schemas.CoinPaymentCreate(
                payee_id=inviter.id,
                amount=settings.INVITE_NEW_USER_COIN_PAYMENT_AMOUNT,
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
        return settings.INVITE_NEW_USER_COIN_PAYMENT_AMOUNT
    return None
