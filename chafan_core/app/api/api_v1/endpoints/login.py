import datetime
import json
from typing import Any, List, Literal, Mapping, Optional
from urllib.parse import parse_qs, urlparse

import logging
logger = logging.getLogger(__name__)

import requests
from fastapi import APIRouter, Body, Depends, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from parsel.selector import Selector
from pydantic import TypeAdapter
from pydantic.types import SecretStr
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas, security
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import (
    check_email,
    client_ip,
    get_redis_cli,
    is_dev,
)
from chafan_core.app.security import (
    check_token_validity_impl,
    generate_password_reset_token,
    verify_password_reset_token,
    create_digit_verification_code,
    register_digit_verification_code,
    check_digit_verification_code,
)
from chafan_core.app.config import settings
from chafan_core.app.email.utils import (
    send_reset_password_email,
    send_verification_code_email,
)
from chafan_core.app.limiter import limiter
from chafan_core.app.materialize import user_schema_from_orm
from chafan_core.app.schemas.coin_deposit import CoinDepositCreate, CoinDepositReference
from chafan_core.app.schemas.event import EventInternal, InviteNewUserInternal
from chafan_core.app.schemas.form import (
    FormField,
    MultipleChoicesField,
    SingleChoiceField,
    TextField,
)
from chafan_core.app.schemas.form_response import (
    FormResponseField,
    MultipleChoiceResponseField,
    SingleChoiceResponseField,
)
from chafan_core.app.schemas.security import (
    LoginWithVerificationCode,
    VerificationCodeRequest,
)

from chafan_core.app.security import get_password_hash
from chafan_core.app.task_utils import execute_with_db
from chafan_core.db.session import ReadSessionLocal
from chafan_core.utils.base import HTTPException_
from chafan_core.utils.validators import (
    CaseInsensitiveEmailStr,
    StrippedNonEmptyBasicStr,
    check_password,
)

router = APIRouter()

# The user's authentication MUST be passed when calling this function
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
    db.commit()
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


def _verify_hcaptcha(hcaptcha_token: str) -> None:
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


@router.post("/login/access-token", response_model=schemas.Token)
def login_access_token(
    request: Request,
    *,
    db: Session = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    email = CaseInsensitiveEmailStr._validate(form_data.username)  # type: ignore

    user = crud.user.authenticate(
        db, email=email, password=SecretStr(form_data.password)
    )
    if not user:
        raise HTTPException_(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return _login_user(db, request=request, user=user)


@router.post(
    "/login-with-verification-code/access-token",
    response_model=schemas.Token,
    include_in_schema=False,
)
def login_with_verification_code_access_token(
    request: Request,
    *,
    db: Session = Depends(deps.get_db),
    login_in: LoginWithVerificationCode,
) -> Any:
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


# TODO should remove out of api
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


@limiter.limit("1/minute")
@router.post("/password-recovery/{email}", response_model=schemas.GenericResponse)
async def recover_password(
    request: Request, email: CaseInsensitiveEmailStr, db: Session = Depends(deps.get_db)
) -> Any:
    """
    Password Recovery
    """
    user = crud.user.get_by_email(db, email=email) #Optional[User]

    if not user:
        raise HTTPException_(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    crud.audit_log.create_with_user(
        db, ipaddr=client_ip(request), user_id=user.id, api=f"Password reset email sent to {email}"
    )
    password_reset_token = generate_password_reset_token(email=email)
    await send_reset_password_email(email=user.email, token=password_reset_token)
    return schemas.GenericResponse()


@router.post("/send-verification-code", response_model=schemas.GenericResponse)
@limiter.limit("1/minute")
async def send_verification_code(
    response: Response, request: Request, *, request_in: VerificationCodeRequest,
    db: Session = Depends(deps.get_db)
) -> Any:

    logger.info(str(request_in))
    logger.info("sending verification")
    if request_in.email is None:
        raise HTTPException_(
            status_code=422,
            detail="Email not provided",
        )
    # TODO audit log should support user_id is NULL. 2025-Jul-06
    crud.audit_log.create_with_user(
        db, ipaddr=client_ip(request), user_id=1, api="send_verification_code to email " + request_in.email
    )
    code = create_digit_verification_code(6)
    await send_verification_code_email(email=request_in.email, code=code)
    await register_digit_verification_code(request_in.email, code)
    # We may switch to trio + hypercorn in future 2025-Jul-06
    #async with trio.open_nursery() as nursery:
    #    nursery.start_soon(send_verification_code_email,email=request_in.email, code=code)
    #    nursery.start_soon(register_digit_verification_code, request_in.email, code)
    return schemas.GenericResponse()


@router.post("/open-account", response_model=schemas.User)
async def create_user_open(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    email: CaseInsensitiveEmailStr = Body(...),
    handle: StrippedNonEmptyBasicStr = Body(...),
    password: SecretStr = Body(...),
    code: str = Body(...),
    invitation_link_uuid: str = Body(...),
) -> Any:
    if (not settings.USERS_OPEN_REGISTRATION):
        raise HTTPException_(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Open user registration is forbidden on this server",
        )
    check_email(email)
    check_password(password)

    db = cached_layer.get_db()

    # TODO audit log should support user_id is NULL. 2025-Jul-06
    crud.audit_log.create_with_user(
        db, ipaddr="0.0.0.0", user_id=1, api="Open new account email " + email
    )
    invitation_link_valid = await cached_layer.try_consume_invitation_link_by_uuid(invitation_link_uuid)
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

    ver_code = await check_digit_verification_code(email, code)
    if not ver_code:
        raise HTTPException_(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The verification code is not present in the system.",
                )
    user_in = schemas.UserCreate(password=password, handle=handle, email=email)
    user = await crud.user.create(db, obj_in=user_in)

    # TODO auto add site
    if False and invitation_link.invited_to_site is not None:
        existing_profile = crud.profile.get_by_user_and_site(
            db, owner_id=user.id, site_id=invitation_link.invited_to_site.id
        )
        if not existing_profile:
            cached_layer.create_site_profile(
                owner=user, site_uuid=invitation_link.invited_to_site.uuid
            )


    # TODO bonus for invite new user, new user's initial coins
    return user_schema_from_orm(user)


@router.post("/check-token-validity/", response_model=schemas.GenericResponse)
def check_token_validity(
    body: str = Body(...),
) -> Any:
    """
    Check JWT token validity
    """
    q = parse_qs(body)
    token = q["token"][0]
    return schemas.GenericResponse(success=check_token_validity_impl(token))


@router.post("/reset-password/", response_model=schemas.GenericResponse)
async def reset_password(
    token: str = Body(...),
    new_password: SecretStr = Body(...),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Reset password
    """
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
    db.commit()
    return schemas.GenericResponse()


@router.get("/unsubscribe", response_class=HTMLResponse, include_in_schema=False)
def unsubscribe(
    *,
    db: Session = Depends(deps.get_db),
    email: CaseInsensitiveEmailStr,
    type: Literal["unread_notifications"],
    unsubscribe_token: str,
) -> Any:
    user = crud.user.get_by_email(db, email=email)
    if user is None:
        raise HTTPException_(status_code=400, detail="Invalid link")
    if user.unsubscribe_token != unsubscribe_token:
        raise HTTPException_(status_code=400, detail="Invalid link")
    if type == "unread_notifications":
        user.enable_deliver_unread_notifications = False
    db.commit()
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
</head>
<body>
    取消成功！
</body>"""


def compute_score_of_form_response(
    form_response: models.FormResponse,
) -> schemas.msg.Scores:
    score = 0
    full_score = 0
    indexed_response_fields = {
        f.unique_name: f
        for f in TypeAdapter(List[FormResponseField]).validate_python(
            form_response.response_fields
        )
    }
    for form_field in TypeAdapter(List[FormField]).validate_python(
        form_response.form.form_fields
    ):
        assert form_field.unique_name in indexed_response_fields
        response_field = indexed_response_fields[form_field.unique_name]
        if isinstance(form_field.field_type, TextField):
            pass
        elif isinstance(form_field.field_type, MultipleChoicesField):
            assert isinstance(response_field.field_content, MultipleChoiceResponseField)
            if form_field.field_type.correct_choices is not None:
                assert form_field.field_type.score_per_correct_choice is not None
                full_score += (
                    len(form_field.field_type.correct_choices)
                    * form_field.field_type.score_per_correct_choice
                )
                for select_choice in response_field.field_content.selected_choices:
                    if select_choice in form_field.field_type.correct_choices:
                        score += form_field.field_type.score_per_correct_choice
                    else:
                        score -= form_field.field_type.score_per_correct_choice
        elif isinstance(form_field.field_type, SingleChoiceField):
            assert isinstance(response_field.field_content, SingleChoiceResponseField)
            if form_field.field_type.correct_choice is not None:
                assert form_field.field_type.score is not None
                full_score += form_field.field_type.score
                if (
                    response_field.field_content.selected_choice
                    == form_field.field_type.correct_choice
                ):
                    score += form_field.field_type.score
        else:
            raise Exception(f"Unknown field: {form_field.field_type}")
    if score < 0:
        score = 0
    return schemas.msg.Scores(
        full_score=full_score,
        score=score,
    )


# TODO Remove this api. put this test in backed
@router.post(
    "/claim-welcome-test-rewards/{id}",
    response_model=schemas.msg.ClaimWelcomeTestScoreMsg,
)
def claim_welcome_test_rewards(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    id: int,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    if current_user.claimed_welcome_test_rewards_with_form_response_id is not None:
        raise HTTPException_(status_code=400, detail="Claimed.")
    form_response = crud.form_response.get(db, id=id)
    if form_response is None:
        raise HTTPException_(status_code=400, detail="Invalid form response id.")
    if not is_dev():
        if form_response.form.uuid != settings.WELCOME_TEST_FORM_UUID:
            raise HTTPException_(status_code=400, detail="Wrong form.")
    if form_response.response_author_id != current_user.id:
        raise HTTPException_(status_code=400, detail="Unauthorized.")
    scores = compute_score_of_form_response(form_response)
    if float(scores.score) < float(scores.full_score) * 0.6:
        return schemas.msg.ClaimWelcomeTestScoreMsg(
            success=False,
            scores=scores,
        )
    current_user.claimed_welcome_test_rewards_with_form_response_id = id
    crud.coin_deposit.make_deposit(
        db,
        obj_in=CoinDepositCreate(
            payee_id=current_user.id,
            amount=scores.score,
            ref_id=CoinDepositReference(
                action="welcome_test_rewards",
                object_id=str(current_user.id),
            ).json(),
            comment="",
        ),
        authorizer_id=current_user.id,
        payee=current_user,
    )
    db.add(current_user)
    db.commit()
    return schemas.msg.ClaimWelcomeTestScoreMsg(
        success=True,
        scores=scores,
    )


# TODO Remove or modify this api. Should not depend on redis directly
@router.get("/category-topics/", response_model=List[schemas.Topic])
def get_category_topics() -> Any:
    redis = get_redis_cli()
    key = "chafan:category-topics"
    value = redis.get(key)
    if value is not None:
        return TypeAdapter(List[schemas.Topic]).validate_json(value)

    def runnable(db: Session) -> List[schemas.Topic]:
        data = [schemas.Topic.from_orm(t) for t in crud.topic.get_category_topics(db)]
        redis.set(
            key, json.dumps(jsonable_encoder(data)), ex=datetime.timedelta(days=1)
        )
        return data

    data = execute_with_db(ReadSessionLocal(), runnable)
    assert data is not None
    return data


_HOSTNAMES_FOR_LINK_PREVIEW = set(
    ["www.flickr.com", "github.com", "twitter.com", "www.zhihu.com"]
)


@router.get("/link-preview/", response_model=Mapping[str, str])
def get_link_preview(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer), *, url: str
) -> Any:
    parsed = urlparse(url)
    if parsed.hostname not in _HOSTNAMES_FOR_LINK_PREVIEW:
        raise HTTPException_(
            status_code=400,
            detail="Invalid hostname for link preview.",
        )
    response_text = cached_layer.request_text(url)
    if not response_text:
        raise HTTPException_(
            status_code=400,
            detail="Unavailable link preview.",
        )
    s = Selector(text=response_text)
    properties = {}
    for e in s.xpath("//meta"):
        if "property" in e.attrib and "content" in e.attrib:
            properties[e.attrib["property"]] = e.attrib["content"]
    title = s.xpath("//title/text()").extract_first()
    if title:
        properties["title"] = title
    return properties
