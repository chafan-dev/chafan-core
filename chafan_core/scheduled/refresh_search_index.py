import time
from typing import Any, Iterator, Mapping

from elasticsearch.client import Elasticsearch
from elasticsearch.helpers import bulk as es_bulk
from sqlalchemy.orm.session import Session

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.app.es import execute_with_es
from chafan_core.app.schemas.answer import AnswerDoc
from chafan_core.app.schemas.article import ArticleDoc
from chafan_core.app.schemas.question import QuestionDoc
from chafan_core.app.schemas.site import SiteDoc
from chafan_core.app.schemas.submission import SubmissionDoc
from chafan_core.app.task_utils import execute_with_db
from chafan_core.db.session import ReadSessionLocal


# This is really expensive
def refresh_search_index() -> None:
    def runnable(db: Session) -> None:
        def question_actions() -> Iterator[Mapping[str, Any]]:
            for question in crud.question.get_all_valid(db):
                doc = QuestionDoc.from_orm(question)
                yield {
                    "_id": doc.id,
                    "_index": f"chafan.{settings.ENV}.question",
                    "_op_type": "index",
                    "_type": "_doc",
                    "doc": doc.dict(),
                }

        def site_actions() -> Iterator[Mapping[str, Any]]:
            for site in crud.site.get_all(db):
                doc = SiteDoc.from_orm(site)
                yield {
                    "_id": doc.id,
                    "_index": f"chafan.{settings.ENV}.site",
                    "_op_type": "index",
                    "_type": "_doc",
                    "doc": doc.dict(),
                }

        def submission_actions() -> Iterator[Mapping[str, Any]]:
            for submission in crud.submission.get_all_valid(db):
                doc = SubmissionDoc.from_orm(submission)
                yield {
                    "_id": doc.id,
                    "_index": f"chafan.{settings.ENV}.submission",
                    "_op_type": "index",
                    "_type": "_doc",
                    "doc": doc.dict(),
                }

        def answer_actions() -> Iterator[Mapping[str, Any]]:
            for answer in crud.answer.get_all_published(db):
                doc = AnswerDoc(
                    id=answer.id,
                    body_prerendered_text=answer.body_prerendered_text,
                    question=QuestionDoc.from_orm(answer.question),
                )
                yield {
                    "_id": doc.id,
                    "_index": f"chafan.{settings.ENV}.answer",
                    "_op_type": "index",
                    "_type": "_doc",
                    "doc": doc.dict(),
                }

        def article_actions() -> Iterator[Mapping[str, Any]]:
            for article in crud.article.get_all_published(db):
                doc = ArticleDoc.from_orm(article)
                yield {
                    "_id": doc.id,
                    "_index": f"chafan.{settings.ENV}.article",
                    "_op_type": "index",
                    "_type": "_doc",
                    "doc": doc.dict(),
                }

        def f(es: Elasticsearch) -> None:
            print("refresh_search_index", flush=True)
            print(es_bulk(es, question_actions(), request_timeout=30))
            time.sleep(5)
            print(es_bulk(es, site_actions(), request_timeout=30))
            time.sleep(5)
            print(es_bulk(es, submission_actions(), request_timeout=30))
            time.sleep(5)
            print(es_bulk(es, answer_actions(), request_timeout=30))
            time.sleep(5)
            print(es_bulk(es, article_actions(), request_timeout=30))

        execute_with_es(f)

    execute_with_db(ReadSessionLocal(), runnable)
