"""Draft content listing service."""

from __future__ import annotations

from typing import List

from chafan_core.app import schemas
from chafan_core.utils.base import filter_not_none


def list_draft_answers(ctx) -> List[schemas.AnswerPreview]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return filter_not_none(
        [
            mat.preview_of_answer(answer)
            for answer in current_user.answers
            if not answer.is_published and answer.body_draft
        ]
    )


def list_draft_articles(ctx) -> List[schemas.ArticlePreview]:
    current_user = ctx.get_current_active_user()
    mat = ctx.principal_view
    return filter_not_none(
        [
            mat.preview_of_article(article)
            for article in current_user.articles
            if not article.is_published or article.body_draft
        ]
    )
