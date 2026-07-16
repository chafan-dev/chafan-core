"""Comment domain service."""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.responders import comment as comment_responder
from chafan_core.app.user_permission import check_user_in_site
from chafan_core.utils.base import HTTPException_


def comment_schema(ctx, comment: models.Comment) -> Optional[schemas.Comment]:
    return comment_responder.comment_schema_from_orm(ctx.principal_view, comment)


def get_comment_schema(ctx, uuid: str) -> Optional[schemas.Comment]:
    comment = crud.comment.get_by_uuid(ctx.get_db(), uuid=uuid)
    if comment is None:
        return None
    return comment_schema(ctx, comment)


def get_comment_upvotes(
    db: Session, *, uuid: str, principal_id: Optional[int]
) -> Optional[schemas.CommentUpvotes]:
    comment = crud.comment.get_by_uuid(db, uuid=uuid)
    if comment is None:
        return None
    valid_upvotes = (
        db.query(models.CommentUpvotes)
        .filter_by(comment_id=comment.id, cancelled=False)
        .count()
    )
    upvoted = False
    if principal_id:
        upvoted = (
            db.query(models.CommentUpvotes)
            .filter_by(comment_id=comment.id, voter_id=principal_id, cancelled=False)
            .first()
            is not None
        )
    return schemas.CommentUpvotes(
        comment_uuid=comment.uuid, count=valid_upvotes, upvoted=upvoted
    )


def delete_comment(db: Session, *, uuid: str, principal_id: int) -> Optional[str]:
    """Returns error message or None on success."""
    comment = crud.comment.get_by_uuid(db, uuid=uuid)
    if comment is None:
        return "The comment doesn't exist in the system."
    if comment.author_id != principal_id:
        return "Unauthorized."
    crud.comment.delete_forever(db, comment=comment)
    return None


def create_comment(
    ctx,
    *,
    comment_in: schemas.CommentCreate,
) -> tuple[models.Comment, schemas.Comment]:
    db = ctx.get_db()
    current_user_id = ctx.unwrapped_principal_id()

    def check_site(site: models.Site) -> None:
        check_user_in_site(
            db,
            site=site,
            user_id=current_user_id,
            op_type=OperationType.WriteSiteComment,
        )

    parents = sum(
        int(id is not None)
        for id in [
            comment_in.question_uuid,
            comment_in.submission_uuid,
            comment_in.answer_uuid,
            comment_in.parent_comment_uuid,
            comment_in.article_uuid,
        ]
    )
    if parents != 1:
        raise HTTPException_(
            status_code=400,
            detail="The comment has too many or too few parent ids.",
        )
    comment = crud.comment.create_with_author(
        db, obj_in=comment_in, author_id=current_user_id, check_site=check_site
    )
    data = comment_schema(ctx, comment)
    assert data is not None
    return comment, data


def update_comment(
    ctx,
    *,
    uuid: str,
    comment_in: schemas.CommentUpdate,
) -> tuple[models.Comment, schemas.Comment, bool]:
    """Returns (updated_comment, schema, was_shared_to_timeline)."""
    db = ctx.get_db()
    current_user_id = ctx.principal_id
    comment = crud.comment.get_by_uuid(db, uuid=uuid)
    if comment is None:
        raise HTTPException_(
            status_code=400,
            detail="The comment doesn't exist in the system.",
        )
    if comment.author_id != current_user_id:
        raise HTTPException_(
            status_code=400,
            detail="The comment is not authored by the current user.",
        )
    if comment.site is not None:
        check_user_in_site(
            db,
            site=comment.site,
            user_id=current_user_id,
            op_type=OperationType.WriteSiteComment,
        )
    was_shared_to_timeline = comment.shared_to_timeline
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    comment_in_dict = comment_in.dict(exclude_none=True)
    comment_in_dict["updated_at"] = utc_now
    new_comment = crud.comment.update(db, db_obj=comment, obj_in=comment_in_dict)
    data = comment_schema(ctx, new_comment)
    assert data is not None
    return new_comment, data, was_shared_to_timeline


def upvote_comment(ctx, *, uuid: str) -> schemas.CommentUpvotes:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    comment = crud.comment.get_by_uuid(db, uuid=uuid)
    if comment is None:
        raise HTTPException_(
            status_code=400,
            detail="The comment doesn't exist in the system.",
        )
    if comment.site:
        check_user_in_site(
            db,
            site=comment.site,
            user_id=current_user.id,
            op_type=OperationType.ReadSite,
        )
    upvoted = (
        db.query(models.CommentUpvotes)
        .filter_by(comment_id=comment.id, voter_id=current_user.id, cancelled=False)
        .first()
        is not None
    )
    if not upvoted:
        if current_user.id == comment.author_id:
            raise HTTPException_(
                status_code=400,
                detail="Author can't upvote authored comment.",
            )
        comment = crud.comment.upvote(db, db_obj=comment, voter=current_user)
        db.commit()
        db.refresh(comment)
    valid_upvotes = (
        db.query(models.CommentUpvotes)
        .filter_by(comment_id=comment.id, cancelled=False)
        .count()
    )
    return schemas.CommentUpvotes(
        comment_uuid=comment.uuid, count=valid_upvotes, upvoted=True
    )


def cancel_upvote_comment(ctx, *, uuid: str) -> schemas.CommentUpvotes:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    comment = crud.comment.get_by_uuid(db, uuid=uuid)
    if comment is None:
        raise HTTPException_(
            status_code=400,
            detail="The comment doesn't exist in the system.",
        )
    if comment.site:
        check_user_in_site(
            db,
            site=comment.site,
            user_id=current_user.id,
            op_type=OperationType.ReadSite,
        )
    upvoted = (
        db.query(models.CommentUpvotes)
        .filter_by(comment_id=comment.id, voter_id=current_user.id, cancelled=False)
        .first()
        is not None
    )
    if upvoted:
        comment = crud.comment.cancel_upvote(db, db_obj=comment, voter=current_user)
        db.commit()
        db.refresh(comment)
    valid_upvotes = (
        db.query(models.CommentUpvotes)
        .filter_by(comment_id=comment.id, cancelled=False)
        .count()
    )
    return schemas.CommentUpvotes(
        comment_uuid=comment.uuid, count=valid_upvotes, upvoted=False
    )
