"""Submission domain service."""

from __future__ import annotations

import datetime
import logging
from typing import List, Optional, Tuple

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas, view_counters
from chafan_core.app.common import OperationType
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.recs.ranking import rank_submissions
from chafan_core.app.responders.archives import submission_archive_schema_from_orm
from chafan_core.app.schemas.event import EventInternal, UpvoteSubmissionInternal
from chafan_core.app.user_permission import check_user_in_site
from chafan_core.utils.base import HTTPException_, filter_not_none
import chafan_core.app.responders as responders

logger = logging.getLogger(__name__)


def submission_schema(ctx, submission: models.Submission):
    return responders.submission.submission_schema_from_orm(ctx, submission)


def recent_k_of_site(ctx, site: models.Site, k: int) -> List[schemas.Submission]:
    return filter_not_none(
        [submission_schema(ctx, s) for s in site.submissions]
    )[:k]


def submissions_for_user(
    ctx, current_user_id: Optional[int]
) -> List[schemas.Submission]:
    db = ctx.get_db()
    if current_user_id:
        current_user = crud.user.get(db, id=current_user_id)
        assert current_user is not None
        submissions: List[schemas.Submission] = []
        for profile in current_user.profiles:
            submissions.extend(recent_k_of_site(ctx, profile.site, k=20))
        if len(submissions) == 0:
            for site in crud.site.get_all_public_readable(db):
                submissions.extend(
                    filter_not_none(
                        [submission_schema(ctx, s) for s in site.submissions]
                    )[:5]
                )
        return rank_submissions(submissions)

    submissions = []
    for site in crud.site.get_all_public_readable(db):
        submissions.extend(
            filter_not_none(
                [submission_schema(ctx, s) for s in site.submissions]
            )[:10]
        )
    return rank_submissions(submissions)


def site_submissions_for_user(
    ctx,
    *,
    site: models.Site,
    user_id: Optional[int],
    skip: int,
    limit: int,
) -> List[schemas.Submission]:
    submissions = rank_submissions(
        filter_not_none(
            [submission_schema(ctx, submission) for submission in site.submissions]
        )
    )
    return submissions[skip : skip + limit]


def list_suggestions(ctx, *, uuid: str):
    from chafan_core.app.common import OperationType
    from chafan_core.app.responders import suggestions as suggestions_responder
    from chafan_core.app.user_permission import check_user_in_site
    from chafan_core.utils.base import HTTPException_

    submission = crud.submission.get_by_uuid(ctx.get_db(), uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    check_user_in_site(
        ctx.get_db(),
        site=submission.site,
        user_id=ctx.unwrapped_principal_id(),
        op_type=OperationType.ReadSite,
    )
    mat = ctx.principal_view
    return filter_not_none(
        [
            suggestions_responder.submission_suggestion_schema_from_orm(mat, s)
            for s in submission.submission_suggestions
        ]
    )


def get_submission(ctx, *, uuid: str) -> schemas.Submission:
    logger.info("get submission " + uuid)
    submission = crud.submission.get_by_uuid(ctx.get_db(), uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    # TODO didn't check principal id
    submission_data = submission_schema(ctx, submission)
    if submission_data is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    return submission_data


def get_upvotes(
    db: Session, *, uuid: str, principal_id: Optional[int]
) -> schemas.SubmissionUpvotes:
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    valid_upvotes = crud.submission.count_upvotes(db, submission)
    if principal_id:
        upvoted = (
            db.query(models.SubmissionUpvotes)
            .filter_by(
                submission_id=submission.id, voter_id=principal_id, cancelled=False
            )
            .first()
            is not None
        )
    else:
        upvoted = False
    return schemas.SubmissionUpvotes(
        submission_uuid=submission.uuid, count=valid_upvotes, upvoted=upvoted
    )


def bump_views(ctx, *, uuid: str) -> None:
    submission = crud.submission.get_by_uuid(ctx.get_db(), uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    view_counters.add_view_async(ctx, "submission", submission.id)


def create_submission(
    ctx,
    *,
    submission_in: schemas.SubmissionCreate,
    author: models.User,
    ipaddr: Optional[str] = None,
) -> Tuple[models.Submission, schemas.Submission]:
    db = ctx.get_db()
    if ipaddr is not None:
        crud.audit_log.create_with_user(
            db,
            ipaddr=ipaddr,
            user_id=author.id,
            api="post submission",
            request_info={"submission_in": jsonable_encoder(submission_in)},
        )
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
            detail="Insufficient coins.",
        )

    new_submission = crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=author.id
    )
    data = submission_schema(ctx, new_submission)
    assert data is not None
    return new_submission, data


def apply_submission_update(
    ctx,
    *,
    submission: models.Submission,
    submission_in: schemas.SubmissionUpdate,
) -> Tuple[models.Submission, Optional[schemas.Submission]]:
    """Apply an update to an existing submission model (used by suggestions accept)."""
    db = ctx.get_db()
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
    return new_submission, submission_schema(ctx, new_submission)


def update_submission(
    ctx,
    *,
    uuid: str,
    submission_in: schemas.SubmissionUpdate,
    ipaddr: Optional[str] = None,
) -> Tuple[models.Submission, Optional[schemas.Submission]]:
    if ipaddr is not None:
        crud.audit_log.create_with_user(
            ctx.get_db(),
            ipaddr=ipaddr,
            user_id=ctx.unwrapped_principal_id(),
            api="post submission",
            request_info={
                "submission_in": jsonable_encoder(submission_in),
                "uuid": uuid,
            },
        )

    submission = crud.submission.get_by_uuid(ctx.get_db(), uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    if ctx.unwrapped_principal_id() != submission.author_id:
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    return apply_submission_update(
        ctx, submission=submission, submission_in=submission_in
    )


def list_archives(
    db: Session, *, uuid: str, principal_id: int
) -> List[schemas.SubmissionArchive]:
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    check_user_in_site(
        db,
        site=submission.site,
        user_id=principal_id,
        op_type=OperationType.ReadSite,
    )
    return [submission_archive_schema_from_orm(a) for a in submission.archives]


def hide_submission(ctx, *, uuid: str) -> Optional[schemas.Submission]:
    db = ctx.get_db()
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
        )
    if (
        submission.site.moderator_id != ctx.principal_id
        and submission.author_id != ctx.principal_id
    ):
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    submission = crud.submission.update(
        db, db_obj=submission, obj_in={"is_hidden": True}
    )
    return submission_schema(ctx, submission)


def upvote_submission(ctx, *, uuid: str) -> schemas.SubmissionUpvotes:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
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
                detail="Insufficient coins.",
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
    return schemas.SubmissionUpvotes(
        submission_uuid=submission.uuid, count=valid_upvotes, upvoted=True
    )


def cancel_upvote_submission(ctx, *, uuid: str) -> schemas.SubmissionUpvotes:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    submission = crud.submission.get_by_uuid(db, uuid=uuid)
    if submission is None:
        raise HTTPException_(
            status_code=400,
            detail="The submission doesn't exist in the system.",
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
    return schemas.SubmissionUpvotes(
        submission_uuid=submission.uuid, count=valid_upvotes, upvoted=False
    )
