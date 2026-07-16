from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.utils.base import filter_not_none

router = APIRouter()


@router.get("/answers/", response_model=List[schemas.AnswerPreview])
def get_draft_answers(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    current_user = ctx.get_current_active_user()
    return filter_not_none(
        [
            ctx.materializer.preview_of_answer(answer)
            for answer in current_user.answers
            if not answer.is_published and answer.body_draft
        ]
    )


@router.get("/articles/", response_model=List[schemas.ArticlePreview])
def get_draft_articles(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    current_user = ctx.get_current_active_user()
    return filter_not_none(
        [
            ctx.materializer.preview_of_article(article)
            for article in current_user.articles
            if not article.is_published or article.body_draft
        ]
    )
