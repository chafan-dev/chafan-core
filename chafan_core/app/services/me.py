"""Current-user (/me) domain helpers."""

from __future__ import annotations

from typing import List, Optional

from chafan_core.app import crud, schemas
from chafan_core.app.responders import misc as misc_responder
from chafan_core.app.services import sites as sites_service
from chafan_core.utils.base import HTTPException_


def list_my_article_columns(ctx) -> List[schemas.ArticleColumn]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        misc_responder.article_column_schema_from_orm(mat, c)
        for c in current_user.article_columns
    ]


def list_subscribed_questions(
    ctx, *, skip: int, limit: int
) -> List[Optional[schemas.QuestionPreview]]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        mat.preview_of_question(q)
        for q in current_user.subscribed_questions[skip : skip + limit]
    ]


def list_bookmarked_answers(
    ctx, *, skip: int, limit: int
) -> List[Optional[schemas.AnswerPreview]]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        mat.preview_of_answer(answer)
        for answer in current_user.bookmarked_answers[skip : skip + limit]
    ]


def list_bookmarked_articles(
    ctx, *, skip: int, limit: int
) -> List[Optional[schemas.ArticlePreview]]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        mat.preview_of_article(article)
        for article in current_user.bookmarked_articles[skip : skip + limit]
    ]


def list_subscribed_article_columns(ctx) -> List[schemas.ArticleColumn]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return [
        misc_responder.article_column_schema_from_orm(mat, c)
        for c in current_user.subscribed_article_columns
    ]


def get_article_column_subscription_after_unsubscribe(
    ctx, *, uuid: str
) -> schemas.UserArticleColumnSubscription:
    db = ctx.get_db()
    article_column = crud.article_column.get_by_uuid(db, uuid=uuid)
    if article_column is None:
        raise HTTPException_(
            status_code=400,
            detail="The article_column doesn't exist in the system.",
        )
    return misc_responder.get_user_article_column_subscription(
        ctx.principal_view, article_column
    )


def list_site_profiles(ctx) -> List[schemas.Profile]:
    return sites_service.site_profiles_for_user(
        ctx.get_db(),
        ctx.principal_view,
        ctx.unwrapped_principal_id(),
    )
