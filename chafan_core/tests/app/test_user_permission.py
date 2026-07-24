"""Unit tests for the article preview read gate.

`article_preview_read_allowed` replaced the `can_read_article` /
`visitor_can_read_article` pair in responders/article.py (D2: one predicate
per resource, "public or authorized", no visitor twin). The two old paths
differed only for anonymous principals reading a non-ANYONE article, so that
branch is pinned here — the API tests all create articles with
`visibility: "anyone"`.
"""

from types import SimpleNamespace

from chafan_core.app.user_permission import article_preview_read_allowed
from chafan_core.utils.base import ContentVisibility

AUTHOR_ID = 1
OTHER_USER_ID = 2


def _article(
    *,
    is_deleted: bool = False,
    is_published: bool = True,
    visibility: ContentVisibility = ContentVisibility.ANYONE,
) -> SimpleNamespace:
    return SimpleNamespace(
        is_deleted=is_deleted,
        is_published=is_published,
        visibility=visibility,
        author_id=AUTHOR_ID,
    )


def test_author_may_read_own_unpublished_article():
    assert article_preview_read_allowed(_article(is_published=False), AUTHOR_ID)


def test_deleted_article_hidden_from_everyone_including_author():
    article = _article(is_deleted=True)
    assert not article_preview_read_allowed(article, AUTHOR_ID)
    assert not article_preview_read_allowed(article, OTHER_USER_ID)
    assert not article_preview_read_allowed(article, None)


def test_unpublished_article_hidden_from_non_authors():
    article = _article(is_published=False)
    assert not article_preview_read_allowed(article, OTHER_USER_ID)
    assert not article_preview_read_allowed(article, None)


def test_live_article_readable_by_any_authenticated_principal():
    """Authenticated non-authors see live articles regardless of visibility."""
    assert article_preview_read_allowed(_article(), OTHER_USER_ID)
    assert article_preview_read_allowed(
        _article(visibility=ContentVisibility.REGISTERED), OTHER_USER_ID
    )


def test_anonymous_requires_anyone_visibility():
    """The one branch where the old visitor twin was stricter."""
    assert article_preview_read_allowed(_article(), None)
    assert not article_preview_read_allowed(
        _article(visibility=ContentVisibility.REGISTERED), None
    )
