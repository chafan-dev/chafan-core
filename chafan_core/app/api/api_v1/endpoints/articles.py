from typing import Any, List

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.param_functions import Query
from sqlalchemy.orm import Session

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.common import client_ip
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import articles as articles_service
from chafan_core.app.services.postprocess import (
    postprocess_new_article,
    postprocess_updated_article,
)
from chafan_core.utils.constants import MAX_ARCHIVE_PAGINATION_LIMIT

router = APIRouter()


@router.get("/{uuid}", response_model=schemas.Article)
def get_article(
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    return articles_service.get_article(ctx, uuid=uuid, request=request)


@router.post("/{uuid}/views/", response_model=schemas.GenericResponse)
def bump_views_counter(
    *,
    uuid: str,
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    articles_service.bump_views(ctx, uuid=uuid)
    return schemas.GenericResponse()


@router.delete("/{uuid}", response_model=schemas.GenericResponse)
def delete_article(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    articles_service.delete_article(
        db, uuid=uuid, principal_id=current_user_id
    )
    return schemas.GenericResponse()


@router.get("/{uuid}/draft", response_model=schemas.article.ArticleDraft)
def get_article_draft(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Get article's draft body as its author.
    """
    return articles_service.get_draft(
        db, uuid=uuid, principal_id=current_user_id
    )


@router.delete("/{uuid}/draft", response_model=schemas.article.ArticleDraft)
def delete_article_draft(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    return articles_service.delete_draft(
        db, uuid=uuid, principal_id=current_user_id
    )


@router.post("/", response_model=schemas.Article)
def create_article(
    request: Request,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    article_in: schemas.ArticleCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Create new article authored by the current user in one of the belonging sites.
    """
    new_article, data = articles_service.create_article(
        ctx, article_in=article_in, ipaddr=client_ip(request)
    )
    if new_article.is_published:
        background_tasks.add_task(postprocess_new_article, new_article.id)
    return data


@router.put("/{uuid}", response_model=schemas.Article)
def update_article(
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
    article_in: schemas.ArticleUpdate,
    background_tasks: BackgroundTasks,
) -> Any:
    article, data, was_published = articles_service.update_article(
        ctx, uuid=uuid, article_in=article_in, ipaddr=client_ip(request)
    )
    if article.is_published:
        background_tasks.add_task(
            postprocess_updated_article, article.id, was_published
        )
    return data


@router.put("/{uuid}/topics/", response_model=schemas.GenericResponse)
def update_article_topics(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    topics_in: schemas.ArticleTopicsUpdate,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    articles_service.update_topics(
        db, uuid=uuid, topics_in=topics_in, principal_id=current_user_id
    )
    return schemas.GenericResponse()


@router.get("/{uuid}/archives/", response_model=List[schemas.ArticleArchive])
def get_article_archives(
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_ARCHIVE_PAGINATION_LIMIT, le=MAX_ARCHIVE_PAGINATION_LIMIT, gt=0
    ),
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Get answer's archives as its author.
    """
    return articles_service.list_archives(
        db, uuid=uuid, principal_id=current_user_id, skip=skip, limit=limit
    )


@router.post("/{uuid}/upvotes/", response_model=schemas.ArticleUpvotes)
def upvote_article(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    return articles_service.upvote_article(ctx, uuid=uuid)


@router.delete("/{uuid}/upvotes/", response_model=schemas.ArticleUpvotes)
def cancel_upvote_article(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    return articles_service.cancel_upvote_article(ctx, uuid=uuid)
