import datetime
from typing import Any, List, Optional, Union

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

import logging
logger = logging.getLogger(__name__)


from chafan_core.app import crud, models, schemas, view_counters
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import OperationType, client_ip, run_dramatiq_task
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.materialize import (
    check_user_in_site,
    submission_archive_schema_from_orm,
)
from chafan_core.app.schemas.event import EventInternal, UpvoteSubmissionInternal
from chafan_core.app.task import (
    postprocess_new_submission,
    postprocess_updated_submission,
)
from chafan_core.utils.base import HTTPException_, filter_not_none

router = APIRouter()


# TODO: paging
@router.get(
    "/",
    response_model=Union[List[schemas.Submission], List[schemas.SubmissionForVisitor]],
)
def get_submissions_for_user(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
) -> Any:
    return cached_layer.get_submissions_for_user()


@router.get(
    "/{uuid}", response_model=Union[schemas.Submission, schemas.SubmissionForVisitor]
)
def get_submission(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    uuid: str,
) -> Any:
    """
    Get submission in one of current_user's belonging sites.
    """
    logger.info("get submission " + uuid)
    submission = crud.submission.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    submission_data: Optional[
        Union[schemas.Submission, schemas.SubmissionForVisitor]
    ] = None
    # TODO didn't check principal id
    submission_data = cached_layer.submission_schema_from_orm(submission)
    if submission_data is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    return submission_data


@router.get("/{uuid}/upvotes/", response_model=schemas.SubmissionUpvotes)
def get_submission_upvotes(
    *,
    db: Session = Depends(deps.get_read_db),
    uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    valid_upvotes = crud.submission.count_upvotes(db, submission)
    if current_user_id:
        upvoted = (
            db.query(models.SubmissionUpvotes)
            .filter_by(
                submission_id=submission.id, voter_id=current_user_id, cancelled=False
            )
            .first()
            is not None
        )
    else:
        upvoted = False
    return schemas.SubmissionUpvotes(
        submission_uuid=submission.uuid, count=valid_upvotes, upvoted=upvoted
    )


@router.post("/{uuid}/views/", response_model=schemas.GenericResponse)
async def bump_views_counter(
    *,
    uuid: str,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
) -> Any:
    submission = crud.submission.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    await view_counters.add_view_async(cached_layer, "submission", submission.id)
    return schemas.GenericResponse()


def _create_submission(
    cached_layer: CachedLayer,
    submission_in: schemas.SubmissionCreate,
    author: models.User,
) -> schemas.Submission:
    db = cached_layer.get_db()
    site = get_site(db, submission_in.site_uuid)
    check_user_in_site(
        db,
        site=site,
        user_id=author.id,
        op_type=OperationType.WriteSiteSubmission,
    )
    if author.remaining_coins < site.create_submission_coin_deduction:
        raise HTTPException_(
            status_code=400,
            detail="Insuffient coins.",
        )

    new_submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=author.id
    )
    run_dramatiq_task(postprocess_new_submission, new_submission.id)
    cached_layer.invalidate_submission_caches(new_submission)
    data = cached_layer.materializer.submission_schema_from_orm(new_submission)
    assert data is not None
    return data


@router.post("/", response_model=schemas.Submission)
def create_submission(
    request: Request,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    submission_in: schemas.SubmissionCreate,
) -> Any:
    """
    Create new submission authored by the current user in one of the belonging sites.
    """
    current_user = cached_layer.get_current_active_user()
    crud.audit_log.create_with_user(
        cached_layer.get_db(),
        ipaddr=client_ip(request),
        user_id=current_user.id,
        api="post submission",
        request_info={"submission_in": jsonable_encoder(submission_in)},
    )
    return _create_submission(cached_layer, submission_in, current_user)


def _update_submission(
    cached_layer: CachedLayer,
    *,
    submission: models.Submission,
    submission_in: schemas.SubmissionUpdate,
) -> Optional[schemas.Submission]:
    db = cached_layer.get_db()
    archive = models.SubmissionArchive(
        submission_id=submission.id,
        title=submission.title,
        description=submission.description,
        description_editor=submission.description_editor,
        description_text=submission.description_text,
        topic_uuids=[t.uuid for t in submission.topics],
        created_at=submission.updated_at,
    )
    db.add(archive)
    submission.archives.append(archive)
    db.commit()
    if submission_in.topic_uuids is not None:
        new_topics = []
        for topic_uuid in submission_in.topic_uuids:
            topic = crud.topic.get_by_uuid(db, uuid=topic_uuid)
            if topic is None:
                raise HTTPException_(
                    status_code=400,
                    detail="The topic doesn't exist.",
                )
            new_topics.append(topic)
        submission_in.topic_uuids = None
        submission = crud.submission.update_topics(
            db, db_obj=submission, new_topics=new_topics
        )
    submission_in_dict = submission_in.dict(exclude_unset=True)
    submission_in_dict["updated_at"] = datetime.datetime.now(tz=datetime.timezone.utc)
    if submission_in.desc:
        del submission_in_dict["desc"]
        submission_in_dict["description"] = submission_in.desc.source
        submission_in_dict["description_editor"] = submission_in.desc.editor
        submission_in_dict["description_text"] = submission_in.desc.rendered_text
    new_submission = crud.submission.update(
        db, db_obj=submission, obj_in=submission_in_dict
    )
    run_dramatiq_task(postprocess_updated_submission, new_submission.id)
    cached_layer.invalidate_submission_caches(new_submission)
    return cached_layer.materializer.submission_schema_from_orm(new_submission)


@router.put("/{uuid}", response_model=schemas.Submission)
def update_submission(
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    submission_in: schemas.SubmissionUpdate,
) -> Any:
    """
    Update submission as author.
    """
    crud.audit_log.create_with_user(
        cached_layer.get_db(),
        ipaddr=client_ip(request),
        user_id=cached_layer.unwrapped_principal_id(),
        api="post submission",
        request_info={"submission_in": jsonable_encoder(submission_in), "uuid": uuid},
    )

    submission = crud.submission.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    if cached_layer.unwrapped_principal_id() != submission.author_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    return _update_submission(
        cached_layer,
        submission=submission,
        submission_in=submission_in,
    )


@router.get("/{uuid}/archives/", response_model=List[schemas.SubmissionArchive])
def get_submission_archives(
    *,
    db: Session = Depends(deps.get_read_db),
    uuid: str,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Get answer's archives as its author.
    """
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    check_user_in_site(
        db,
        site=submission.site,
        user_id=current_user_id,
        op_type=OperationType.ReadSite,
    )
    return [submission_archive_schema_from_orm(a) for a in submission.archives]


@router.get("/{uuid}/suggestions/", response_model=List[schemas.SubmissionSuggestion])
def get_submission_suggestions(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
) -> Any:
    submission = crud.submission.get_by_uuid(cached_layer.get_db(), uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    check_user_in_site(
        cached_layer.get_db(),
        site=submission.site,
        user_id=cached_layer.unwrapped_principal_id(),
        op_type=OperationType.ReadSite,
    )
    return filter_not_none(
        [
            cached_layer.materializer.submission_suggestion_schema_from_orm(s)
            for s in submission.submission_suggestions
        ]
    )


@router.put("/{uuid}/hide", response_model=schemas.Submission)
def hide_submission(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    db: Session = Depends(deps.get_db),
    uuid: str,
) -> Any:
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    if (
        submission.site.moderator_id != cached_layer.principal_id
        and submission.author_id != cached_layer.principal_id
    ):
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    submission = crud.submission.update(
        db, db_obj=submission, obj_in={"is_hidden": True}
    )
    cached_layer.invalidate_submission_caches(submission)
    return cached_layer.materializer.submission_schema_from_orm(submission)


@router.post("/{uuid}/upvotes/", response_model=schemas.SubmissionUpvotes)
def upvote_submission(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Upvote submission as the current user.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    check_user_in_site(
        db,
        site=submission.site,
        user_id=current_user.id,
        op_type=OperationType.ReadSite,
    )
    upvoted = (
        db.query(models.SubmissionUpvotes)
        .filter_by(
            submission_id=submission.id, voter_id=current_user.id, cancelled=False
        )
        .first()
        is not None
    )
    if not upvoted:
        if current_user.id == submission.author_id:
            raise HTTPException_(
                status_code=400,
                detail="Author can't upvote authored submission.",
            )
        if (
            current_user.remaining_coins
            < submission.site.upvote_submission_coin_deduction
        ):
            raise HTTPException_(
                status_code=400,
                detail="Insuffient coins.",
            )
        upvoted_before = (
            db.query(models.SubmissionUpvotes)
            .filter_by(submission_id=submission.id, voter_id=current_user.id)
            .first()
            is not None
        )
        # Don't swap the statements before and after!
        submission = crud.submission.upvote(db, db_obj=submission, voter=current_user)
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        if not upvoted_before:
            crud.coin_payment.make_payment(
                db,
                obj_in=schemas.CoinPaymentCreate(
                    payee_id=submission.author_id,
                    amount=submission.site.upvote_submission_coin_deduction,
                    event_json=EventInternal(
                        created_at=utc_now,
                        content=UpvoteSubmissionInternal(
                            subject_id=current_user.id,
                            submission_id=submission.id,
                        ),
                    ).json(),
                ),
                payer=current_user,
                payee=submission.author,
            )
        db.commit()
        db.refresh(submission)
    valid_upvotes = (
        db.query(models.SubmissionUpvotes)
        .filter_by(submission_id=submission.id, cancelled=False)
        .count()
    )
    cached_layer.invalidate_submission_caches(submission)
    return schemas.SubmissionUpvotes(
        submission_uuid=submission.uuid, count=valid_upvotes, upvoted=True
    )


@router.delete("/{uuid}/upvotes/", response_model=schemas.SubmissionUpvotes)
def cancel_upvote_submission(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Cancel upvote for submission as the current user.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exists in the system.",
        )
    check_user_in_site(
        db,
        site=submission.site,
        user_id=current_user.id,
        op_type=OperationType.ReadSite,
    )
    upvoted = (
        db.query(models.SubmissionUpvotes)
        .filter_by(
            submission_id=submission.id, voter_id=current_user.id, cancelled=False
        )
        .first()
        is not None
    )
    if upvoted:
        submission = crud.submission.cancel_upvote(
            db, db_obj=submission, voter=current_user
        )
        db.commit()
        db.refresh(submission)
    valid_upvotes = (
        db.query(models.SubmissionUpvotes)
        .filter_by(submission_id=submission.id, cancelled=False)
        .count()
    )
    cached_layer.invalidate_submission_caches(submission)
    return schemas.SubmissionUpvotes(
        submission_uuid=submission.uuid, count=valid_upvotes, upvoted=False
    )
