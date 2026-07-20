from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from fastapi.param_functions import Query
from sqlalchemy.orm import Session

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import sites as sites_service
from chafan_core.utils.constants import MAX_SITE_QUESTIONS_PAGINATION_LIMIT

router = APIRouter()


@router.post("/", response_model=schemas.CreateSiteResponse)
def create_site(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    site_in: schemas.SiteCreate,
) -> Any:
    """
    Create new site as user.
    """
    return sites_service.create_site_for_user(ctx, site_in=site_in)


@router.put("/{uuid}/config", response_model=schemas.Site, include_in_schema=False)
def config_site(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
    site_in: schemas.SiteUpdate,
) -> Any:
    """
    Configure a site as moderator.
    """
    return sites_service.config_site(ctx, uuid=uuid, site_in=site_in)


@router.get("/{subdomain}", response_model=schemas.Site)
def get_site_info(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
    subdomain: str,
) -> Any:
    """
    Get a site's basic info.
    """
    return sites_service.get_site_info_for_user(
        ctx, subdomain=subdomain, current_user_id=current_user_id
    )


@router.get("/{uuid}/questions/", response_model=List[schemas.QuestionPreview])
def get_site_questions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_SITE_QUESTIONS_PAGINATION_LIMIT,
        le=MAX_SITE_QUESTIONS_PAGINATION_LIMIT,
        gt=0,
    ),
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    """
    Get a site's questions.
    """
    return sites_service.list_site_questions(
        ctx, uuid=uuid, skip=skip, limit=limit
    )


@router.get(
    "/{uuid}/submissions/",
    response_model=List[schemas.Submission],
)
def get_site_submissions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_SITE_QUESTIONS_PAGINATION_LIMIT,
        le=MAX_SITE_QUESTIONS_PAGINATION_LIMIT,
        gt=0,
    ),
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    """
    Get a site's submissions.
    """
    return sites_service.list_site_submissions(
        ctx,
        uuid=uuid,
        skip=skip,
        limit=limit,
        current_user_id=current_user_id,
    )


@router.get("/{uuid}/apply", response_model=schemas.SiteApplicationResponse)
def get_site_apply(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Check application to site membership.
    """
    return sites_service.get_site_apply(
        db, uuid=uuid, current_user_id=current_user_id
    )


@router.post("/{uuid}/apply", response_model=schemas.SiteApplicationResponse)
def site_apply(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    """
    Apply to site membership.
    """
    return sites_service.site_apply(ctx, uuid=uuid)


@router.delete("/{uuid}/membership", response_model=schemas.GenericResponse)
def remove_my_site_membership(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    sites_service.remove_my_site_membership(ctx, uuid=uuid)
    return schemas.GenericResponse()


@router.get("/{uuid}/webhooks/", response_model=List[schemas.Webhook])
def get_webhooks(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    return sites_service.get_webhooks(ctx, uuid=uuid)


@router.get("/{uuid}/related/", response_model=List[schemas.Site])
def get_related(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    return sites_service.get_related_sites(ctx, uuid=uuid)
