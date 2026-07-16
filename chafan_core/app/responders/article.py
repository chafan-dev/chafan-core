from typing import Optional
import logging

from chafan_core.app import crud, models, schemas, user_permission, view_counters
from chafan_core.app.schemas.article import ArticleInDB
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import filter_not_none

logger = logging.getLogger(__name__)


def article_schema_from_orm(
    cached_layer, article: models.Article, principal_id
) -> Optional[schemas.Article]:
    db = cached_layer.broker.get_db()
    if not user_permission.article_read_allowed(db, article, principal_id):
        return None

    upvoted = False
    bookmarked = False
    if principal_id is not None:
        upvoted = (
            db.query(models.ArticleUpvotes)
            .filter_by(article_id=article.id, voter_id=principal_id, cancelled=False)
            .first()
            is not None
        )
        principal = crud.user.get(db, id=principal_id)
        if principal is not None:
            bookmarked = article in principal.bookmarked_articles

    base = ArticleInDB.from_orm(article)
    d = base.dict()
    d["article_column"] = cached_layer.materializer.article_column_schema_from_orm(
        article.article_column
    )
    d["comments"] = filter_not_none(
        [cached_layer.materializer.comment_schema_from_orm(c) for c in article.comments]
    )
    d["bookmark_count"] = article.bookmarkers.count()
    d["bookmarked"] = bookmarked
    d["author"] = cached_layer.materializer.preview_of_user(article.author)
    d["upvoted"] = upvoted
    d["view_times"] = view_counters.get_viewcount_article(
        cached_layer.broker, article.id
    )
    d["archives_count"] = len(article.archives)

    if article.is_published:
        body = article.body
    else:
        # Drafts: only the author may read (enforced by article_read_allowed).
        if principal_id != article.author_id:
            return None
        body = article.body_draft if article.body_draft else article.body

    d["content"] = RichText(
        source=body, editor=article.editor, rendered_text=article.body_text
    )
    return schemas.Article(**d)
