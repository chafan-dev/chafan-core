import datetime
import json
from typing import Any, List, Literal, Mapping
from urllib.parse import urlparse

import logging
logger = logging.getLogger(__name__)

from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from parsel.selector import Selector
from pydantic import TypeAdapter
from pydantic.types import SecretStr
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.common import (
    get_redis_cli,
)
from chafan_core.app.config import settings
from chafan_core.app.limiter import limiter
from chafan_core.app.schemas.coin_deposit import CoinDepositCreate, CoinDepositReference
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
from chafan_core.app.services import accounts as accounts_service
from chafan_core.app.services import auth as auth_service
from chafan_core.app.services import notifications as notifications_service
from chafan_core.app.infra.runtime import execute_with_db
from chafan_core.db.session import SessionLocal
from chafan_core.utils.base import HTTPException_
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
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    id: int,
) -> Any:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    if current_user.claimed_welcome_test_rewards_with_form_response_id is not None:
        raise HTTPException_(status_code=400, detail="Claimed.")
    form_response = crud.form_response.get(db, id=id)
    if form_response is None:
        raise HTTPException_(status_code=400, detail="Invalid form response id.")
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

    data = execute_with_db(SessionLocal(), runnable)
    assert data is not None
    return data


_HOSTNAMES_FOR_LINK_PREVIEW = set(
    ["www.flickr.com", "github.com", "twitter.com", "www.zhihu.com"]
)


@router.get("/link-preview/", response_model=Mapping[str, str])
def get_link_preview(
    ctx: RequestContext = Depends(deps.get_request_context), *, url: str
) -> Any:
    parsed = urlparse(url)
    if parsed.hostname not in _HOSTNAMES_FOR_LINK_PREVIEW:
        raise HTTPException_(
            status_code=400,
            detail="Invalid hostname for link preview.",
        )
    from chafan_core.app.services import link_preview

    response_text = link_preview.request_text(url)
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
