from typing import Any, Dict, List, Optional, Union

import sentry_sdk
from elasticsearch.client import Elasticsearch

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.app.es import execute_with_es
from chafan_core.app.schemas.answer import AnswerDoc
from chafan_core.app.schemas.article import ArticleDoc
from chafan_core.app.schemas.question import QuestionDoc
from chafan_core.app.schemas.site import SiteDoc
from chafan_core.app.schemas.submission import SubmissionDoc
from chafan_core.db.session import ReadSessionLocal
from chafan_core.utils.constants import indexed_object_T


# https://www.elastic.co/guide/en/elasticsearch/reference/current/full-text-queries.html
def es_search(
    index_type: indexed_object_T,
    query: str,
    env: str = settings.ENV,
) -> Optional[List[int]]:
    if not settings.ES_ENDPOINT:
        if index_type == "site":
            return [s.id for s in crud.site.get_all(ReadSessionLocal())]
        return None

    def f(es: Elasticsearch) -> Optional[List[int]]:
        query_body: Dict[str, Any] = {}
        if index_type == "question":
            query_body = {
                "multi_match": {
                    "fields": ["doc.description_text", "doc.title"],
                    "query": query,
                    "fuzziness": "AUTO",
                }
            }
        elif index_type == "answer":
            query_body = {
                "multi_match": {
                    "fields": [
                        "doc.body_prerendered_text",
                        "doc.question.title",
                        "doc.question.description_text",
                    ],
                    "query": query,
                    "fuzziness": "AUTO",
                }
            }
        elif index_type == "submission":
            query_body = {
                "multi_match": {
                    "fields": ["doc.title", "doc.description_text"],
                    "query": query,
                    "fuzziness": "AUTO",
                }
            }
        elif index_type == "article":
            query_body = {
                "multi_match": {
                    "fields": ["doc.body_prerendered_text", "doc.title"],
                    "query": query,
                    "fuzziness": "AUTO",
                }
            }
        elif index_type == "site":
            query_body = {
                "multi_match": {
                    "fields": ["doc.description", "doc.name", "doc.subdomain"],
                    "query": query,
                    "fuzziness": "AUTO",
                }
            }
        else:
            sentry_sdk.capture_message(f"Unknown index_type: {index_type}")
            return None
        es_results = es.search(
            body={"query": query_body, "_source": ["doc.id"]},
            index=f"chafan.{env}.{index_type}",
            doc_type="_doc",
        )
        return [hit["_source"]["doc"]["id"] for hit in es_results["hits"]["hits"]]

    return execute_with_es(f)


def es_index_doc(
    doc: Union[QuestionDoc, AnswerDoc, ArticleDoc, SubmissionDoc, SiteDoc]
) -> None:
    def f(es: Elasticsearch) -> None:
        if isinstance(doc, QuestionDoc):
            index_type = "question"
        elif isinstance(doc, AnswerDoc):
            index_type = "answer"
        elif isinstance(doc, ArticleDoc):
            index_type = "article"
        elif isinstance(doc, SubmissionDoc):
            index_type = "submission"
        elif isinstance(doc, SiteDoc):
            index_type = "site"
        else:
            sentry_sdk.capture_message(f"Unknown doc type: {doc}")
            return
        index = f"chafan.{settings.ENV}.{index_type}"
        es.index(
            index=index,
            id=str(doc.id),
            doc_type="_doc",
            document={"doc": doc.dict()},
        )
        es.indices.refresh(index=index)

    execute_with_es(f)
