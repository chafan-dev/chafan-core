from typing import Optional
import logging

from chafan_core.app import crud, models, schemas, user_permission
from chafan_core.app.responders._util import get_db, shaper
from chafan_core.app.schemas.article import ArticleInDB
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import filter_not_none

logger = logging.getLogger(__name__)


def preview_of_article(ctx, article: models.Article) -> Optional[schemas.ArticlePreview]:
    principal_id = ctx.principal_id
    if not user_permission.article_preview_read_allowed(article, principal_id):
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
    d["view_times"] = crud.viewcount.get_viewcount_article(db, article.id)
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
