"""Authentication, access tokens and credential recovery.

Everything here is the *decision* side of authentication: verifying a
credential, minting a token, issuing and checking the codes/tokens that stand
in for one. Rate limiting and captcha enforcement are HTTP concerns and stay in
`api/`; only the outbound hCaptcha call lives here.
"""

from __future__ import annotations

import datetime
import logging
from urllib.parse import parse_qs

import requests
from fastapi import Request, status
from pydantic.types import SecretStr
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas, security
from chafan_core.app.common import client_ip, get_redis_cli
from chafan_core.app.config import settings
from chafan_core.app.email.utils import (
    send_reset_password_email,
    send_verification_code_email,
)
from chafan_core.app.schemas.security import (
    LoginWithVerificationCode,
    VerificationCodeRequest,
)
from chafan_core.app.security import (
    check_token_validity_impl,
    create_digit_verification_code,
    generate_password_reset_token,
    get_password_hash,
    register_digit_verification_code,
    verify_password_reset_token,
)
from chafan_core.utils.base import HTTPException_
from chafan_core.utils.validators import CaseInsensitiveEmailStr, check_password

logger = logging.getLogger(__name__)


# The user's authentication MUST have been verified before calling this.
def _login_user(db: Session, *, request: Request, user: models.User) -> schemas.Token:
    if not crud.user.is_active(user):
        raise HTTPException_(status_code=400, detail="Inactive user")
    access_token_expires = datetime.timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    if user.flags is None:
        user.flags = ""
    # TODO This should be moved to another component
    if "activated" not in user.flags.split():
        user.flags += " activated"  # Used to decide whether to resend invitation email
    ipaddr = client_ip(request)
    crud.audit_log.create_with_user(
        db, ipaddr=ipaddr, user_id=user.id, api="create access token"
    )
    return schemas.Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        token_type="bearer",
    )


def login_with_password(
    db: Session, *, request: Request, username: str, password: str
) -> schemas.Token:
    """OAuth2 password grant: verify the credential and mint a token."""
    email = CaseInsensitiveEmailStr._validate(username)  # type: ignore

    user = crud.user.authenticate(db, email=email, password=SecretStr(password))
    if not user:
        raise HTTPException_(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return _login_user(db, request=request, user=user)


def login_with_verification_code(
    db: Session, *, request: Request, login_in: LoginWithVerificationCode
) -> schemas.Token:
    redis_cli = get_redis_cli()
    phone_number_str = login_in.phone_number.format_e164()
    key = f"chafan:verification-code:{phone_number_str}"
    value = redis_cli.get(key)
    raise HTTPException_(
        status_code=400,
        detail="login with verification code is blocked",
    )
    if value is None:
        raise HTTPException_(
            status_code=400,
            detail="The verification code is not present in the system.",
        )
    if value != login_in.code:
        raise HTTPException_(
            status_code=400,
            detail="Invalid verification code.",
        )
    redis_cli.delete(key)
    user = crud.user.get_by_phone_number(db, phone_number=login_in.phone_number)
    if user is None:
        raise HTTPException_(
            status_code=400,
            detail="No such account.",
        )
    return _login_user(db, request=request, user=user)


def verify_hcaptcha(hcaptcha_token: str) -> None:
    """Outbound hCaptcha check. Whether a captcha is required is decided in api/."""
    r = requests.post(
        "https://hcaptcha.com/siteverify",
        data={
            "sitekey": settings.HCAPTCHA_SITEKEY,
            "secret": settings.HCAPTCHA_SECRET,
            "response": hcaptcha_token,
        },
    )
    if not r.ok or not r.json()["success"]:
        raise HTTPException_(status_code=400, detail="Incorrect hCaptcha")


def recover_password(
    db: Session, *, request: Request, email: CaseInsensitiveEmailStr
) -> schemas.GenericResponse:
    user = crud.user.get_by_email(db, email=email)  # Optional[User]

    if not user:
        raise HTTPException_(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    crud.audit_log.create_with_user(
        db,
        ipaddr=client_ip(request),
        user_id=user.id,
        api=f"Password reset email sent to {email}",
    )
    password_reset_token = generate_password_reset_token(email=email)
    send_reset_password_email(email=user.email, token=password_reset_token)
    return schemas.GenericResponse()


def send_verification_code(
    db: Session, *, request: Request, request_in: VerificationCodeRequest
) -> schemas.GenericResponse:
    logger.info(str(request_in))
    logger.info("sending verification")
    if request_in.email is None:
        raise HTTPException_(
            status_code=422,
            detail="Email not provided",
        )
    # TODO audit log should support user_id is NULL. 2025-Jul-06
    crud.audit_log.create_with_user(
        db,
        ipaddr=client_ip(request),
        user_id=1,
        api="send_verification_code to email " + request_in.email,
    )
    code = create_digit_verification_code(6)
    send_verification_code_email(email=request_in.email, code=code)
    register_digit_verification_code(request_in.email, code)
    # We may switch to trio + hypercorn in future 2025-Jul-06
    # async with trio.open_nursery() as nursery:
    #    nursery.start_soon(send_verification_code_email,email=request_in.email, code=code)
    #    nursery.start_soon(register_digit_verification_code, request_in.email, code)
    return schemas.GenericResponse()


def check_token_validity(*, body: str) -> schemas.GenericResponse:
    """Check JWT token validity. `body` is the raw urlencoded request body."""
    q = parse_qs(body)
    token = q["token"][0]
    return schemas.GenericResponse(success=check_token_validity_impl(token))


def reset_password(
    db: Session, *, token: str, new_password: SecretStr
) -> schemas.GenericResponse:
    check_password(new_password)
    email = verify_password_reset_token(token)
    if not email:
        raise HTTPException_(status_code=400, detail="Invalid token")
    user = crud.user.get_by_email(db, email=email)
    if not user:
        raise HTTPException_(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    elif not crud.user.is_active(user):
        raise HTTPException_(status_code=400, detail="Inactive user")
    crud.audit_log.create_with_user(
        db, ipaddr="0.0.0.0", user_id=user.id, api="Reset password with token"
    )
    hashed_password = get_password_hash(new_password)
    user.hashed_password = hashed_password
    db.add(user)
    return schemas.GenericResponse()
