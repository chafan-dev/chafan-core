from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from fastapi.param_functions import Query

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.common import get_logger
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import people as people_service
from chafan_core.utils.constants import (
    MAX_USER_ANSWERS_PAGINATION_LIMIT,
    MAX_USER_ARTICLES_PAGINATION_LIMIT,
    MAX_USER_FOLLOWERS_PAGINATION_LIMIT,
    MAX_USER_QUESTIONS_PAGINATION_LIMIT,
    MAX_USER_SUBMISSIONS_PAGINATION_LIMIT,
)
from chafan_core.utils.validators import StrippedNonEmptyBasicStr

router = APIRouter()
logger = get_logger(__name__)


@router.get("/{handle}", response_model=schemas.UserPublic)
def get_user_public(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    handle: StrippedNonEmptyBasicStr,
) -> Any:
    logger.debug("Call get_user_public")
    return people_service.get_user_public(ctx, handle=handle)


@router.get("/{uuid}/site-profiles/", response_model=List[schemas.Profile])
def get_user_site_profiles(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    return people_service.list_user_site_profiles(
        ctx, uuid=uuid, current_user_id=current_user_id
    )


@router.get("/{uuid}/questions/", response_model=List[schemas.QuestionPreview])
def get_user_questions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_QUESTIONS_PAGINATION_LIMIT,
        le=MAX_USER_QUESTIONS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    """
    Get a user's asked questions.
    """
    return people_service.list_user_questions(ctx, uuid=uuid, skip=skip, limit=limit)


@router.get("/{uuid}/submissions/", response_model=List[schemas.Submission])
def get_user_submissions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_SUBMISSIONS_PAGINATION_LIMIT,
        le=MAX_USER_SUBMISSIONS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    """
    Get a user's submissions.
    """
    return people_service.list_user_submissions(ctx, uuid=uuid, skip=skip, limit=limit)


@router.get("/{uuid}/articles/", response_model=List[schemas.ArticlePreview])
def get_user_articles(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_ARTICLES_PAGINATION_LIMIT,
        le=MAX_USER_ARTICLES_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    return people_service.list_user_articles(ctx, uuid=uuid, skip=skip, limit=limit)


@router.get(
    "/{uuid}/answers/",
    response_model=List[schemas.AnswerPreview],
)
def get_user_answers(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_ANSWERS_PAGINATION_LIMIT,
        le=MAX_USER_ANSWERS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    """
    Get a user's authored answers.
    """
    return people_service.list_user_answers(ctx, uuid=uuid, skip=skip, limit=limit)


@router.get("/{uuid}/work-exps/", response_model=List[schemas.UserWorkExperience])
def get_user_work_exps(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    return people_service.list_user_work_exps(ctx, uuid=uuid)


@router.get("/{uuid}/edu-exps/", response_model=List[schemas.UserEducationExperience])
def get_user_edu_exps(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    return people_service.list_user_edu_exps(ctx, uuid=uuid)


@router.get("/{uuid}/followers/", response_model=List[schemas.UserPreview])
def get_user_followers(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_FOLLOWERS_PAGINATION_LIMIT,
        le=MAX_USER_FOLLOWERS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    return people_service.list_user_followers(ctx, uuid=uuid, skip=skip, limit=limit)


@router.get("/{uuid}/followed/", response_model=List[schemas.UserPreview])
def get_user_followed(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_USER_FOLLOWERS_PAGINATION_LIMIT,
        le=MAX_USER_FOLLOWERS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    return people_service.list_user_followed(ctx, uuid=uuid, skip=skip, limit=limit)


@router.get("/{uuid}/related/", response_model=List[schemas.UserPreview])
def get_related(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    return people_service.list_related_users(ctx, uuid=uuid)
