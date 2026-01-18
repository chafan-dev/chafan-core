import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import OperationType, run_dramatiq_task
from chafan_core.app.materialize import check_user_in_site
from chafan_core.app.task import postprocess_comment_update, postprocess_new_comment
from chafan_core.utils.base import HTTPException_

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{uuid}", response_model=schemas.Comment)
def get_comment(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    uuid: str,
) -> Any:
    """
    Get a comment in one of the current user's belonging sites.
    """
    comment = crud.comment.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if comment is None:
        raise HTTPException_(
            status_code=400,
            detail="The comment doesn't exists in the system.",
        )
    current_user_id = cached_layer.principal_id
    if current_user_id:
        if comment.site is not None:
            check_user_in_site(
                cached_layer.get_db(),
                site=comment.site,
                user_id=current_user_id,
                op_type=OperationType.ReadSite,
            )
        return cached_layer.materializer.comment_schema_from_orm(comment)
    else:
        if comment.site is not None:
            if not comment.site.public_readable:
                raise HTTPException_(
                    status_code=400,
                    detail="Unauthorized.",
                )
        return cached_layer.materializer.comment_for_visitor_schema_from_orm(comment)


@router.get("/{uuid}/upvotes/", response_model=schemas.CommentUpvotes)
def get_comment_upvotes(
    *,
    db: Session = Depends(deps.get_read_db),
    uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    comment = crud.comment.get_by_uuid(db, uuid=uuid)
    if comment is None:
        raise HTTPException_(
            status_code=400,
            detail="The comment doesn't exists in the system.",
        )
    valid_upvotes = (
        db.query(models.CommentUpvotes)
        .filter_by(comment_id=comment.id, cancelled=False)
        .count()
    )
    if current_user_id:
        upvoted = (
            db.query(models.CommentUpvotes)
            .filter_by(comment_id=comment.id, voter_id=current_user_id, cancelled=False)
            .first()
            is not None
        )
    else:
        upvoted = False
    return schemas.CommentUpvotes(
        comment_uuid=comment.uuid, count=valid_upvotes, upvoted=upvoted
    )


@router.delete("/{uuid}", response_model=schemas.GenericResponse)
def delete_comment(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    db: Session = Depends(deps.get_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    comment = crud.comment.get_by_uuid(db, uuid=uuid)
    if comment is None:
        raise HTTPException_(
            status_code=400,
            detail="The comment doesn't exists in the system.",
        )
    if comment.author_id != current_user_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    crud.comment.delete_forever(db, comment=comment)
    cached_layer.invalidate_comment_caches(comment)
    return schemas.GenericResponse()


@router.post("/", response_model=schemas.Comment)
def create_comment(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    db: Session = Depends(deps.get_db),
    comment_in: schemas.CommentCreate,
) -> Any:
    """
    Create new comment authored by the current active user in one of the belonging sites.
    """
    current_user_id = cached_layer.unwrapped_principal_id()

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
    run_dramatiq_task(
        postprocess_new_comment,
        comment.id,
        comment_in.shared_to_timeline,
        comment_in.mentioned,
    )
    comment_data = cached_layer.materializer.comment_schema_from_orm(comment)
    cached_layer.invalidate_comment_caches(comment)
    assert comment_data is not None
    return comment_data


@router.put("/{uuid}", response_model=schemas.Comment)
def update_comment(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    comment_in: schemas.CommentUpdate,
) -> Any:
    """
    Update comment authored by the current user in one of the belonging sites.
    """
    current_user_id = cached_layer.principal_id
    comment = crud.comment.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if comment is None:
        raise HTTPException_(
            status_code=400,
            detail="The comment doesn't exists in the system.",
        )
    if comment.author_id != current_user_id:
        raise HTTPException_(
            status_code=400,
            detail="The comment is not authored by the current user.",
        )
    if comment.site is not None:
        check_user_in_site(
            cached_layer.get_db(),
            site=comment.site,
            user_id=current_user_id,
            op_type=OperationType.WriteSiteComment,
        )
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    comment_in_dict = comment_in.dict(exclude_none=True)
    comment_in_dict["updated_at"] = utc_now
    was_shared_to_timeline = comment.shared_to_timeline
    new_comment = crud.comment.update(
        cached_layer.get_db(), db_obj=comment, obj_in=comment_in_dict
    )
    run_dramatiq_task(
        postprocess_comment_update,
        comment.id,
        was_shared_to_timeline,
        shared_to_timeline=comment_in.shared_to_timeline,
        mentioned=comment_in.mentioned,
    )
    cached_layer.invalidate_comment_caches(new_comment)
    comment_data = cached_layer.materializer.comment_schema_from_orm(new_comment)
    assert comment_data is not None
    return comment_data


@router.post("/{uuid}/upvotes/", response_model=schemas.CommentUpvotes)
def upvote_comment(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Upvote comment as the current user.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    comment = crud.comment.get_by_uuid(db, uuid=uuid)
    if comment is None:
        raise HTTPException_(
            status_code=400,
            detail="The comment doesn't exists in the system.",
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
        # Don't swap the statements before and after!
        comment = crud.comment.upvote(db, db_obj=comment, voter=current_user)
        db.commit()
        db.refresh(comment)
    valid_upvotes = (
        db.query(models.CommentUpvotes)
        .filter_by(comment_id=comment.id, cancelled=False)
        .count()
    )
    # FIXME: maybe returning upvotes from a different endpoint thus using different caching logic.
    cached_layer.invalidate_comment_caches(comment)
    return schemas.CommentUpvotes(
        comment_uuid=comment.uuid, count=valid_upvotes, upvoted=True
    )


@router.delete("/{uuid}/upvotes/", response_model=schemas.CommentUpvotes)
def cancel_upvote_comment(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Cancel upvote for comment as the current user.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    comment = crud.comment.get_by_uuid(db, uuid=uuid)
    if comment is None:
        raise HTTPException_(
            status_code=400,
            detail="The comment doesn't exists in the system.",
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
    cached_layer.invalidate_comment_caches(comment)
    return schemas.CommentUpvotes(
        comment_uuid=comment.uuid, count=valid_upvotes, upvoted=False
    )
