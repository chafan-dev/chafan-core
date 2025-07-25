from typing import Optional
import logging
logger = logging.getLogger(__name__)

from chafan_core.app import crud, models, schemas
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import (
    filter_not_none,
)

from chafan_core.app.schemas.article import ArticleInDB
from chafan_core.app.schemas.article_archive import ArticleArchiveInDB


from chafan_core.app import view_counters


def article_schema_from_orm(
    cached_layer, article: models.Article, principal_id
) -> Optional[schemas.Article]:
    # TODO need to check if the user is allowed to read this article
    upvoted = (
        cached_layer.broker.get_db()
        .query(models.ArticleUpvotes)
        .filter_by(
            article_id=article.id, voter_id=principal_id, cancelled=False
        )
        .first()
        is not None
    )
    base = ArticleInDB.from_orm(article)
    d = base.dict()
    d["article_column"] = cached_layer.materializer.article_column_schema_from_orm(
        article.article_column
    )
    d["comments"] = filter_not_none(
        [cached_layer.materializer.comment_schema_from_orm(c) for c in article.comments]
    )
    d["bookmark_count"] = article.bookmarkers.count()
    principal = crud.user.get(cached_layer.broker.get_db(), id=principal_id)
    #assert principal is not None
    #d["bookmarked"] = article in principal.bookmarked_articles
    d["bookmarked"] = True # TODO leave it for now 2025-07-24
    d["author"] = cached_layer.materializer.preview_of_user(article.author)
    d["upvoted"] = upvoted
    d["view_times"] = view_counters.get_viewcount_article(cached_layer.broker, article.id)
    d["archives_count"] = len(article.archives)
    if article.is_published:
        body = article.body
    else:
        if article.body_draft:
            body = article.body_draft
        else:
            body = article.body
    d["content"] = RichText(
        source=body, editor=article.editor, rendered_text=article.body_text
    )
    return schemas.Article(**d)
