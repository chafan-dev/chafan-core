"""Search domain service."""

from __future__ import annotations

from typing import List

from chafan_core.app import crud, models, schemas
from chafan_core.app.responders.question import preview_of_question_as_search_hit
from chafan_core.app.services import sites as sites_service
from chafan_core.app.services import submissions as submissions_service
from chafan_core.utils.base import filter_not_none


def search_users(ctx, q: str) -> List[schemas.UserPreview]:
    if q == "":
        return []
    users = crud.user.search_by_handle_or_full_name(ctx.get_db(), fragment=q)
    return [ctx.preview_of_user(u) for u in users]


def search_sites(ctx, q: str) -> List[schemas.Site]:
    if q == "":
        return []
    sites = crud.site.search(ctx.get_db(), fragment=q)
    return [sites_service.site_schema(ctx, s) for s in sites]


def search_topics(ctx, q: str) -> List[schemas.Topic]:
    if q == "":
        return []
    return crud.topic.get_ilike(ctx.get_db(), fragment=q, column=models.Topic.name)


def search_questions(ctx, q: str) -> List[schemas.QuestionPreviewForSearch]:
    if q == "":
        return []
    questions = crud.question.search(ctx.get_db(), q=q)
    # TODO no search hit limit
    return filter_not_none([preview_of_question_as_search_hit(qq) for qq in questions])


def search_articles(ctx, q: str) -> List[schemas.ArticlePreview]:
    if q == "":
        return []
    articles = crud.article.search(ctx.get_db(), q=q)
    mat = ctx.materializer
    return filter_not_none([mat.preview_of_article(a) for a in articles])


def search_submissions(ctx, q: str) -> List[schemas.Submission]:
    if q == "":
        return []
    submissions = crud.submission.search(ctx.get_db(), q=q)
    return filter_not_none(
        [submissions_service.submission_schema(ctx, s) for s in submissions]
    )


def search_answers(ctx, q: str) -> List[schemas.AnswerPreview]:
    if q == "":
        return []
    answers = crud.answer.search(ctx.get_db(), q=q)
    mat = ctx.materializer
    return filter_not_none([mat.preview_of_answer(a) for a in answers])
