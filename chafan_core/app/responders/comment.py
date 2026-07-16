"""Comment ORM → API schema shaping."""

from __future__ import annotations

from typing import Optional

from chafan_core.app import models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import filter_not_none


def root_route(comment: models.Comment) -> Optional[str]:
    if comment.answer is not None:
        return (
            f"/questions/{comment.answer.question.uuid}/answers/{comment.answer.uuid}"
        )
    if comment.question is not None:
        return f"/questions/{comment.question.uuid}"
    if comment.article is not None:
        return f"/articles/{comment.article.uuid}"
    if comment.submission is not None:
        return f"/submissions/{comment.submission.uuid}"
    if comment.parent_comment is not None:
        return root_route(comment.parent_comment)
    return None


def comment_schema_from_orm(mat, comment: models.Comment) -> Optional[schemas.Comment]:
    """Shape a comment for mat.principal_id. mat is Materializer (db + principal + previews)."""
    from chafan_core.app.user_permission import user_in_site

    db = mat.broker.get_db()
    if comment.site and not user_in_site(
        db,
        site=comment.site,
        user_id=mat.principal_id,
        op_type=OperationType.ReadSite,
    ):
        return None
    base = schemas.CommentInDBBase.from_orm(comment)
    upvoted = False
    if mat.principal_id is not None:
        upvoted = (
            db.query(models.CommentUpvotes)
            .filter_by(
                comment_id=comment.id,
                voter_id=mat.principal_id,
                cancelled=False,
            )
            .first()
            is not None
        )
    d = base.dict()
    d["author"] = mat.preview_of_user(comment.author)
    d["upvoted"] = upvoted
    d["root_route"] = root_route(comment)
    d["content"] = RichText(
        source=comment.body,
        rendered_text=comment.body_text,
        editor=comment.editor,
    )
    d["child_comments"] = filter_not_none(
        [comment_schema_from_orm(mat, c) for c in comment.child_comments]
    )
    return schemas.Comment(**d)
