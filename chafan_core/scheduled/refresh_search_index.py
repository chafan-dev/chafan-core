import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm.session import Session
from whoosh import writing  # type: ignore
from whoosh.index import create_in  # type: ignore
from whoosh.index import open_dir

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.app.search import schemas
from chafan_core.app.task_utils import execute_with_db
from chafan_core.db.session import ReadSessionLocal
from chafan_core.utils.constants import indexed_object_T


@contextmanager
def _index_rewriter(index_type: indexed_object_T) -> Iterator[writing.IndexWriter]:
    index_dir = settings.SEARCH_INDEX_FILESYSTEM_PATH + "/" + index_type
    schema = schemas[index_type]
    if os.path.exists(index_dir):
        ix = open_dir(index_dir)
    else:
        # Initialize search index
        os.makedirs(index_dir)
        ix = create_in(index_dir, schema)
    writer = ix.writer()

    try:
        yield writer
    finally:
        writer.commit(mergetype=writing.CLEAR)


def refresh_search_index() -> None:
    def runnable(db: Session) -> None:
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

    execute_with_db(ReadSessionLocal(), runnable)
