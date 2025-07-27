import os
from typing import List, Mapping, Optional

from jieba.analyse.analyzer import ChineseAnalyzer  # type: ignore
from whoosh.analysis.analyzers import StemmingAnalyzer  # type: ignore
from whoosh.fields import ID  # type: ignore
from whoosh.fields import TEXT, Schema
from whoosh.index import open_dir  # type: ignore
from whoosh.qparser import MultifieldParser  # type: ignore

from chafan_core.app.config import settings
from chafan_core.utils.constants import indexed_object_T

import logging
logger = logging.getLogger(__name__)

_analyzer = ChineseAnalyzer()
_stemming_analyzer = StemmingAnalyzer()

QUESTION_SCHEMA = Schema(
    id=ID(stored=True, unique=True),
    title=TEXT(analyzer=_analyzer, field_boost=2.0),
    description_text=TEXT(analyzer=_analyzer),
)

SITE_SCHEMA = Schema(
    id=ID(stored=True, unique=True),
    name=TEXT(analyzer=_analyzer, field_boost=2.0),
    description=TEXT(analyzer=_analyzer),
    subdomain=TEXT(field_boost=2.0, analyzer=_stemming_analyzer),
)

SUBMISSION_SCHEMA = Schema(
    id=ID(stored=True, unique=True),
    title=TEXT(analyzer=_analyzer, field_boost=2.0),
    description_text=TEXT(analyzer=_analyzer),
)

ANSWER_SCHEMA = Schema(
    id=ID(stored=True, unique=True),
    body_prerendered_text=TEXT(analyzer=_analyzer),
    question_title=TEXT(analyzer=_analyzer),
    question_description_text=TEXT(analyzer=_analyzer),
)

ARTICLE_SCHEMA = Schema(
    id=ID(stored=True, unique=True),
    title=TEXT(analyzer=_analyzer, field_boost=2.0),
    body_text=TEXT(analyzer=_analyzer),
)

schemas: Mapping[indexed_object_T, Schema] = {
    "question": QUESTION_SCHEMA,
    "site": SITE_SCHEMA,
    "submission": SUBMISSION_SCHEMA,
    "answer": ANSWER_SCHEMA,
    "article": ARTICLE_SCHEMA,
}


def do_search(
    index_type: indexed_object_T,
    query: str,
    index_dir_prefix: Optional[str] = None,
) -> Optional[List[int]]:
    if index_dir_prefix is None:
        index_dir_prefix = settings.SEARCH_INDEX_FILESYSTEM_PATH + "/"
    index_dir = index_dir_prefix + index_type
    if not os.path.exists(index_dir):
        logger.error(f"index_dir not exist, search skipped {index_dir}")
        return None
    ix = open_dir(index_dir)
    with ix.searcher() as searcher:
        parser = MultifieldParser(
            [n for n in ix.schema.names() if n != "id"],
            schema=ix.schema,
        )
        q = parser.parse(query)
        results = searcher.search(q)
        return [int(r["id"]) for r in results]
