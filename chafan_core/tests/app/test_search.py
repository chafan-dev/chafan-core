import os
import shutil
from contextlib import contextmanager
from typing import Iterator

from whoosh import writing  # type: ignore
from whoosh.analysis.analyzers import FancyAnalyzer  # type: ignore
from whoosh.analysis.analyzers import LanguageAnalyzer, StemmingAnalyzer
from whoosh.index import create_in  # type: ignore

from chafan_core.app.search import do_search, schemas
from chafan_core.utils.constants import indexed_object_T

_TEST_SEARCH_INDEX_PREFIX = "/tmp/test_chafan_search/"


@contextmanager
def _index_writer(index_type: indexed_object_T) -> Iterator[writing.IndexWriter]:
    index_dir = _TEST_SEARCH_INDEX_PREFIX + index_type
    schema = schemas[index_type]
    if os.path.exists(index_dir):
        shutil.rmtree(index_dir)

    # Initialize search index
    os.makedirs(index_dir)
    ix = create_in(index_dir, schema)
    writer = ix.writer()

    try:
        yield writer
    finally:
        writer.commit(mergetype=writing.CLEAR)


def test_search_sites() -> None:
    with _index_writer("site") as writer:
        writer.add_document(
            id="1", name="投资", description="test", subdomain="investment"
        )

    ids = do_search("site", "投资", _TEST_SEARCH_INDEX_PREFIX)
    assert ids == [1], ids

    ids = do_search("site", "invest", _TEST_SEARCH_INDEX_PREFIX)
    assert ids == [1], ids

    ids = do_search("site", "investment", _TEST_SEARCH_INDEX_PREFIX)
    assert ids == [1], ids


def test_stemming_anlayzer() -> None:
    ana = StemmingAnalyzer()
    parsed = [token.text for token in ana("investment")]
    assert parsed == ["invest"], parsed


def test_fancy_anlayzer() -> None:
    ana = FancyAnalyzer()
    parsed = [token.text for token in ana("investment")]
    assert parsed == ["investment"], parsed


def test_lang_en_anlayzer() -> None:
    ana = LanguageAnalyzer("en")
    parsed = [token.text for token in ana("investment")]
    assert parsed == ["invest"], parsed
