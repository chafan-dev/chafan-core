from typing import Optional
import logging

from chafan_core.app import crud, models, schemas, user_permission, view_counters
from chafan_core.app.model_utils import is_live_article
from chafan_core.app.responders._util import get_db, shaper
from chafan_core.app.schemas.article import ArticleInDB
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import ContentVisibility, filter_not_none

logger = logging.getLogger(__name__)


def can_read_article(*, article: models.Article, principal_id: int) -> bool:
    if article.is_deleted:
        return False
    if principal_id == article.author_id:
        return True
    return is_live_article(article)


def visitor_can_read_article(*, article: models.Article) -> bool:
    if not is_live_article(article):
        return False
    return article.visibility == ContentVisibility.ANYONE


def preview_of_article(ctx, article: models.Article) -> Optional[schemas.ArticlePreview]:
    principal_id = ctx.principal_id
    if principal_id:
        if not can_read_article(article=article, principal_id=principal_id):
            return None
    else:
        if not visitor_can_read_article(article=article):
            return None
    mat = shaper(ctx)
    return schemas.ArticlePreview(
        uuid=article.uuid,
        author=mat.preview_of_user(article.author),
        article_column=mat.article_column_schema_from_orm(article.article_column),
        title=article.title,
        body_text=article.body_text,
        is_published=article.is_published,
        upvotes_count=article.upvotes_count,
    )


def article_schema_from_orm(
    ctx, article: models.Article, principal_id
) -> Optional[schemas.Article]:
    db = get_db(ctx)
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

    mat = shaper(ctx)
    base = ArticleInDB.from_orm(article)
    d = base.dict()
    d["article_column"] = mat.article_column_schema_from_orm(article.article_column)
    d["comments"] = filter_not_none(
        [mat.comment_schema_from_orm(c) for c in article.comments]
    )
    d["bookmark_count"] = article.bookmarkers.count()
    d["bookmarked"] = bookmarked
    d["author"] = mat.preview_of_user(article.author)
    d["upvoted"] = upvoted
    d["view_times"] = view_counters.get_viewcount_article(ctx, article.id)
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
