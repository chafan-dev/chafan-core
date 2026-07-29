from typing import Any, List, Literal, Mapping

from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic.types import SecretStr
from sqlalchemy.orm import Session

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.limiter import limiter
from chafan_core.app.schemas.security import (
    LoginWithVerificationCode,
    VerificationCodeRequest,
)
from chafan_core.app.services import accounts as accounts_service
from chafan_core.app.services import auth as auth_service
from chafan_core.app.services import link_preview as link_preview_service
from chafan_core.app.services import notifications as notifications_service
from chafan_core.app.services import topics as topics_service
from chafan_core.app.services import welcome_test as welcome_test_service
from chafan_core.utils.validators import (
    CaseInsensitiveEmailStr,
    StrippedNonEmptyBasicStr,
)

router = APIRouter()


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
    return auth_service.login_with_password(
        db,
        request=request,
        username=form_data.username,
        password=form_data.password,
    )


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
    return auth_service.login_with_verification_code(
        db, request=request, login_in=login_in
    )


# NOTE: @limiter.limit sits *above* @router.post here, so the router registered
# the undecorated function and this limit never applies. Pre-existing; preserved
# deliberately -- moving it would be a behavior change, not a refactor.
@limiter.limit("1/minute")
@router.post("/password-recovery/{email}", response_model=schemas.GenericResponse)
def recover_password(
    request: Request, email: CaseInsensitiveEmailStr, db: Session = Depends(deps.get_db)
) -> Any:
    """
    Password Recovery
    """
    return auth_service.recover_password(db, request=request, email=email)


@router.post("/send-verification-code", response_model=schemas.GenericResponse)
@limiter.limit("1/minute")
def send_verification_code(
    response: Response, request: Request, *, request_in: VerificationCodeRequest,
    db: Session = Depends(deps.get_db)
) -> Any:
    return auth_service.send_verification_code(
        db, request=request, request_in=request_in
    )


@router.post("/open-account", response_model=schemas.User)
def create_user_open(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    email: CaseInsensitiveEmailStr = Body(...),
    handle: StrippedNonEmptyBasicStr = Body(...),
    password: SecretStr = Body(...),
    code: str = Body(...),
    invitation_link_uuid: str = Body(...),
) -> Any:
    return accounts_service.open_account(
        ctx,
        email=email,
        handle=handle,
        password=password,
        code=code,
        invitation_link_uuid=invitation_link_uuid,
    )


@router.post("/check-token-validity/", response_model=schemas.GenericResponse)
def check_token_validity(
    body: str = Body(...),
) -> Any:
    """
    Check JWT token validity
    """
    return auth_service.check_token_validity(body=body)


@router.post("/reset-password/", response_model=schemas.GenericResponse)
def reset_password(
    token: str = Body(...),
    new_password: SecretStr = Body(...),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Reset password
    """
    return auth_service.reset_password(db, token=token, new_password=new_password)


@router.get("/unsubscribe", response_class=HTMLResponse, include_in_schema=False)
def unsubscribe(
    *,
    db: Session = Depends(deps.get_db),
    email: CaseInsensitiveEmailStr,
    type: Literal["unread_notifications"],
    unsubscribe_token: str,
) -> Any:
    notifications_service.unsubscribe_by_email_token(
        db, email=email, type=type, unsubscribe_token=unsubscribe_token
    )
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
</head>
<body>
    取消成功！
</body>"""


# TODO Remove this api. put this test in backed
@router.post(
    "/claim-welcome-test-rewards/{id}",
    response_model=schemas.msg.ClaimWelcomeTestScoreMsg,
)
def claim_welcome_test_rewards(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    id: int,
) -> Any:
    return welcome_test_service.claim_welcome_test_rewards(ctx, form_response_id=id)


@router.get("/category-topics/", response_model=List[schemas.Topic])
def get_category_topics() -> Any:
    return topics_service.get_category_topics()


@router.get("/link-preview/", response_model=Mapping[str, str])
def get_link_preview(
    # `ctx` is unused, but removing it would drop this operation's
    # OAuth2PasswordBearer security entry from the OpenAPI document.
    ctx: RequestContext = Depends(deps.get_request_context),
    *,
    url: str,
) -> Any:
    return link_preview_service.get_link_preview(url)
