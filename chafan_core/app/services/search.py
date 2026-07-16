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
    mat = ctx.principal_view
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
    mat = ctx.principal_view
    return filter_not_none([mat.preview_of_answer(a) for a in answers])


# --- index rebuild (scheduled) -------------------------------------------------

import logging
import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm.session import Session
from whoosh import writing  # type: ignore
from whoosh.index import create_in  # type: ignore
from whoosh.index import open_dir

from chafan_core.app.config import settings
from chafan_core.app.infra.runtime import execute_with_db
from chafan_core.app.search import schemas as whoosh_schemas
from chafan_core.db.session import SessionLocal
from chafan_core.utils.constants import indexed_object_T

_logger = logging.getLogger(__name__)


@contextmanager
def _index_rewriter(index_type: indexed_object_T) -> Iterator[writing.IndexWriter]:
    index_dir = settings.SEARCH_INDEX_FILESYSTEM_PATH + "/" + index_type
    schema = whoosh_schemas[index_type]
    if os.path.exists(index_dir):
        ix = open_dir(index_dir)
    else:
        os.makedirs(index_dir)
        ix = create_in(index_dir, schema)
    writer = ix.writer()
    try:
        yield writer
    finally:
        writer.commit(mergetype=writing.CLEAR)


def refresh_search_index() -> None:
    def runnable(db: Session) -> None:
        _logger.info("refresh_search_index executed")
        with _index_rewriter("question") as writer:
            for q in crud.question.get_all_valid(db):
                writer.add_document(
                    id=str(q.id), title=q.title, description_text=q.description_text
                )
        with _index_rewriter("site") as writer:
            for s in crud.site.get_all(db):
                writer.add_document(
                    id=str(s.id),
                    name=s.name,
                    description=s.description,
                    subdomain=s.subdomain,
                )
        with _index_rewriter("submission") as writer:
            for submission in crud.submission.get_all_valid(db):
                writer.add_document(
                    id=str(submission.id),
                    title=submission.title,
                    description_text=submission.description_text,
                )
        with _index_rewriter("answer") as writer:
            for a in crud.answer.get_all_published(db):
                writer.add_document(
                    id=str(a.id),
                    body_prerendered_text=a.body_prerendered_text,
                    question_title=a.question.title,
                    question_description_text=a.question.description_text,
                )
        with _index_rewriter("article") as writer:
            for article in crud.article.get_all_published(db):
                writer.add_document(
                    id=str(article.id),
                    title=article.title,
                    body_text=article.body_text,
                )

    execute_with_db(SessionLocal(), runnable)
