"""Question domain service."""

from __future__ import annotations

import datetime
from typing import List, Optional, Tuple

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, schemas, user_permission, view_counters
from chafan_core.app.common import OperationType
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.recs.ranking import rank_answers
from chafan_core.app.schemas.event import (
    EventInternal,
    InviteAnswerInternal,
    UpvoteQuestionInternal,
)
from chafan_core.app.user_permission import check_user_in_site, user_in_site
from chafan_core.utils.base import HTTPException_, filter_not_none
import chafan_core.app.responders as responders


def get_question_model(db: Session, uuid: str) -> Optional[models.Question]:
    return crud.question.get_by_uuid(db, uuid=uuid)


def get_question_by_id(db: Session, question_id: int) -> Optional[models.Question]:
    return crud.question.get_by_id(db, id=question_id)


def get_question_model_http(db: Session, uuid: str) -> models.Question:
    question = get_question_model(db, uuid)
    if question is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exist in the system.",
        )
    return question


def get_readable_question(
    db: Session,
    *,
    uuid: str,
    principal_id: Optional[int],
    ctx,
) -> Optional[models.Question]:
    """Fetch question if principal may read it (hidden-question gate)."""
    question = get_question_model(db, uuid)
    if question is None:
        return None
    if not user_permission.question_read_allowed(ctx, question, principal_id):
        return None
    return question


def question_schema(ctx, question: models.Question) -> Optional[schemas.Question]:
    return responders.question.question_schema_from_orm(
        ctx, ctx.principal_id, question, ctx
    )


def require_question_schema(ctx, question: models.Question) -> schemas.Question:
    question_data = question_schema(ctx, question)
    if question_data is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exist in the system.",
        )
    return question_data


def get_question(ctx, *, uuid: str) -> schemas.Question:
    question = get_readable_question(
        ctx.get_db(),
        uuid=uuid,
        principal_id=ctx.principal_id,
        ctx=ctx,
    )
    if question is None:
        raise HTTPException_(
            status_code=404,
            detail="The question doesn't exist in the system.",
        )
    if question.is_hidden:
        raise HTTPException_(
            status_code=403,
            detail="Not allowed to access this quesion",
        )
    return require_question_schema(ctx, question)


def bump_views(ctx, *, uuid: str) -> None:
    question = get_question_model_http(ctx.get_db(), uuid)
    view_counters.add_view_async(ctx, "question", question.id)


def get_question_subscription(
    ctx, question: models.Question
) -> Optional[schemas.UserQuestionSubscription]:
    current_user = ctx.try_get_current_user()
    if not current_user:
        return None
    return schemas.UserQuestionSubscription(
        question_uuid=question.uuid,
        subscription_count=question.subscribers.count(),
        subscribed_by_me=(question in current_user.subscribed_questions),
    )


def list_answer_previews(ctx, question: models.Question) -> list[schemas.AnswerPreview]:
    mat = ctx.principal_view
    return sorted(
        filter_not_none(
            [mat.preview_of_answer(answer) for answer in question.answers]
        ),
        key=lambda a: a.upvotes_count,
    )


def get_question_answers(
    ctx, *, uuid: str, principal_id: Optional[int]
) -> List[schemas.AnswerPreview]:
    question = get_question_model_http(ctx.get_db(), uuid)
    if not user_in_site(
        ctx.get_db(),
        site=question.site,
        user_id=principal_id,
        op_type=OperationType.ReadSite,
    ):
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    return list_answer_previews(ctx, question)


def create_question(
    ctx,
    *,
    question_in: schemas.QuestionCreate,
    ipaddr: Optional[str] = None,
) -> Tuple[models.Question, Optional[schemas.Question]]:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    if ipaddr is not None:
        crud.audit_log.create_with_user(
            db,
            ipaddr=ipaddr,
            user_id=current_user.id,
            api="post question",
            request_info={"question_in": jsonable_encoder(question_in)},
        )

    site = get_site(db, question_in.site_uuid)
    check_user_in_site(
        db,
        site=site,
        user_id=current_user.id,
        op_type=OperationType.WriteSiteQuestion,
    )
    if current_user.remaining_coins < site.create_question_coin_deduction:
        raise HTTPException_(
            status_code=400,
            detail="Insufficient coins.",
        )
    new_question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=current_user.id
    )
    # Subscribed to the authored question automatically
    crud.user.subscribe_question(
        db, db_obj=current_user, question=new_question
    )
    return new_question, question_schema(ctx, new_question)


def update_question(
    ctx,
    *,
    uuid: str,
    question_in: schemas.QuestionUpdate,
    current_user_id: int,
    ipaddr: Optional[str] = None,
) -> Tuple[models.Question, Optional[schemas.Question]]:
    db = ctx.get_db()
    if ipaddr is not None:
        crud.audit_log.create_with_user(
            db,
            ipaddr=ipaddr,
            user_id=current_user_id,
            api="put question",
            request_info={"question_in": jsonable_encoder(question_in), "uuid": uuid},
        )

    question = crud.question.get_by_uuid(db, uuid=uuid)
    if question is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exist in the system.",
        )
    if current_user_id != question.author_id:
        if not user_in_site(
            db,
            user_id=current_user_id,
            site=question.site,
            op_type=OperationType.WriteSiteQuestion,
        ):
            raise HTTPException_(
                status_code=400,
                detail="Unauthorized.",
            )
    editor_id = question.editor_id
    if editor_id is None:
        editor_id = question.author_id
    archive = models.QuestionArchive(
        question_id=question.id,
        title=question.title,
        description=question.description,
        description_text=question.description_text,
        description_editor=question.description_editor,
        created_at=question.updated_at,
        editor_id=editor_id,
    )
    archive.topics = question.topics
    db.add(archive)
    question.archives.append(archive)
    db.commit()
    if question_in.topic_uuids is not None:
        new_topics = []
        for topic_uuid in question_in.topic_uuids:
            topic = crud.topic.get_by_uuid(db, uuid=topic_uuid)
            if topic is None:
                raise HTTPException_(
                    status_code=400,
                    detail="The topic doesn't exist.",
                )
            new_topics.append(topic)
        question_in.topic_uuids = None
        question = crud.question.update_topics(
            db, db_obj=question, new_topics=new_topics
        )
    question_in_dict = question_in.dict(exclude_none=True)
    question_in_dict["editor_id"] = current_user_id
    question_in_dict["updated_at"] = datetime.datetime.now(tz=datetime.timezone.utc)
    if question_in.desc:
        question_in_dict["description"] = question_in.desc.source
        question_in_dict["description_editor"] = question_in.desc.editor
        question_in_dict["description_text"] = question_in.desc.rendered_text
    else:
        question_in_dict["description"] = None
        question_in_dict["description_text"] = None
    new_question = crud.question.update(db, db_obj=question, obj_in=question_in_dict)
    return new_question, question_schema(ctx, new_question)


def list_archives(ctx, *, uuid: str) -> list[schemas.QuestionArchive]:
    from chafan_core.app.responders import archives as archives_responder

    question = get_question_model_http(ctx.get_db(), uuid)
    mat = ctx.principal_view
    return [
        archives_responder.question_archive_schema_from_orm(mat, a)
        for a in question.archives
    ]


def get_upvotes(ctx, *, uuid: str) -> schemas.QuestionUpvotes:
    question = get_question_model_http(ctx.get_db(), uuid)
    return ctx.principal_view.get_question_upvotes(question)


def hide_question(ctx, *, uuid: str) -> Optional[schemas.Question]:
    question = get_question_model_http(ctx.get_db(), uuid)
    if (
        question.site.moderator_id != ctx.principal_id
        and question.author_id != ctx.principal_id
    ):
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    question = crud.question.update(
        ctx.get_db(), db_obj=question, obj_in={"is_hidden": True}
    )
    return question_schema(ctx, question)


def invite_answer(ctx, *, uuid: str, user_uuid: str) -> None:
    question = get_question_model_http(ctx.get_db(), uuid)
    check_user_in_site(
        ctx.get_db(),
        site=question.site,
        user_id=ctx.unwrapped_principal_id(),
        op_type=OperationType.ReadSite,
    )
    invited_user = crud.user.get_by_uuid(ctx.get_db(), uuid=user_uuid)
    if invited_user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exist in the system.",
        )
    if invited_user.id == ctx.unwrapped_principal_id():
        raise HTTPException_(
            status_code=400,
            detail="You can't invite yourself.",
        )
    check_user_in_site(
        ctx.get_db(),
        site=question.site,
        user_id=invited_user.id,
        op_type=OperationType.WriteSiteQuestion,
    )
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    crud.notification.create_with_content(
        ctx.broker,
        receiver_id=invited_user.id,
        event=EventInternal(
            created_at=utc_now,
            content=InviteAnswerInternal(
                subject_id=ctx.unwrapped_principal_id(),
                question_id=question.id,
                user_id=invited_user.id,
            ),
        ),
    )


def upvote_question(ctx, *, uuid: str) -> schemas.QuestionUpvotes:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    question = get_question_model_http(ctx.get_db(), uuid)
    check_user_in_site(
        db,
        site=question.site,
        user_id=current_user.id,
        op_type=OperationType.ReadSite,
    )
    upvoted = (
        db.query(models.QuestionUpvotes)
        .filter_by(question_id=question.id, voter_id=current_user.id, cancelled=False)
        .first()
        is not None
    )
    if not upvoted:
        if current_user.id == question.author_id:
            raise HTTPException_(
                status_code=400,
                detail="Author can't upvote authored question.",
            )
        if current_user.remaining_coins < question.site.upvote_question_coin_deduction:
            raise HTTPException_(
                status_code=400,
                detail="Insufficient coins.",
            )
        upvoted_before = (
            db.query(models.QuestionUpvotes)
            .filter_by(question_id=question.id, voter_id=current_user.id)
            .first()
            is not None
        )
        # Don't swap the statements before and after!
        question = crud.question.upvote(db, db_obj=question, voter=current_user)
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        if not upvoted_before:
            crud.coin_payment.make_payment(
                db,
                obj_in=schemas.CoinPaymentCreate(
                    payee_id=question.author_id,
                    amount=question.site.upvote_question_coin_deduction,
                    event_json=EventInternal(
                        created_at=utc_now,
                        content=UpvoteQuestionInternal(
                            subject_id=current_user.id,
                            question_id=question.id,
                        ),
                    ).json(),
                ),
                payer=current_user,
                payee=question.author,
            )
        db.commit()
        db.refresh(question)
    valid_upvotes = (
        db.query(models.QuestionUpvotes)
        .filter_by(question_id=question.id, cancelled=False)
        .count()
    )
    return schemas.QuestionUpvotes(
        question_uuid=question.uuid, count=valid_upvotes, upvoted=True
    )


def cancel_upvote_question(ctx, *, uuid: str) -> schemas.QuestionUpvotes:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    question = crud.question.get_by_uuid(db, uuid=uuid)
    if question is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exist in the system.",
        )
    check_user_in_site(
        db,
        site=question.site,
        user_id=current_user.id,
        op_type=OperationType.ReadSite,
    )
    upvoted = (
        db.query(models.QuestionUpvotes)
        .filter_by(question_id=question.id, voter_id=current_user.id, cancelled=False)
        .first()
        is not None
    )
    if upvoted:
        question = crud.question.cancel_upvote(db, db_obj=question, voter=current_user)
        db.commit()
        db.refresh(question)
    valid_upvotes = (
        db.query(models.QuestionUpvotes)
        .filter_by(question_id=question.id, cancelled=False)
        .count()
    )
    return schemas.QuestionUpvotes(
        question_uuid=question.uuid, count=valid_upvotes, upvoted=False
    )


def get_question_page(ctx, *, uuid: str, request=None) -> schemas.QuestionPage:
    from chafan_core.app.services import answers as answers_service
    from chafan_core.app.services import audit as audit_service

    current_user_id = ctx.principal_id
    question = get_readable_question(
        ctx.get_db(),
        uuid=uuid,
        principal_id=current_user_id,
        ctx=ctx,
    )
    if question is None:
        if request is not None:
            audit_service.create_audit(
                ctx.get_db(),
                api=f"get_question_page {uuid} retrieved None",
                request=request,
                user_id=current_user_id,
            )
        raise HTTPException_(
            status_code=404,
            detail="No such question",
        )
    question_data = require_question_schema(ctx, question)
    flags = schemas.QuestionPageFlags()
    if ctx.principal_id:
        if question.author_id == ctx.principal_id:
            flags.editable = True
            flags.hideable = True
        if user_in_site(
            ctx.get_db(),
            site=question.site,
            user_id=ctx.principal_id,
            op_type=OperationType.WriteSiteQuestion,
        ):
            flags.editable = True
        if user_in_site(
            ctx.get_db(),
            site=question.site,
            user_id=ctx.principal_id,
            op_type=OperationType.WriteSiteAnswer,
        ):
            flags.answer_writable = True
        if user_in_site(
            ctx.get_db(),
            site=question.site,
            user_id=ctx.principal_id,
            op_type=OperationType.WriteSiteComment,
        ):
            flags.comment_writable = True
        if question.site.moderator_id == ctx.principal_id:
            flags.is_mod = True
            flags.hideable = True
    # TODO 2025-07-08 This is hacky. The whole logic of question flags needs to be reviewed and simplified.
    if question.site.public_writable_answer:
        flags.answer_writable = True
    return schemas.QuestionPage(
        question=question_data,
        # TODO: continuation
        # TODO: rethink the internal caching
        full_answers=filter_not_none(
            [
                answers_service.answer_schema(ctx, answer)
                for answer in rank_answers(
                    question.answers, principal_id=ctx.principal_id
                )
            ]
        ),
        answer_previews=filter_not_none(
            [
                ctx.preview_of_answer(answer)
                for answer in rank_answers(
                    question.answers, principal_id=ctx.principal_id
                )
            ]
        ),
        question_subscription=get_question_subscription(ctx, question),
        flags=flags,
    )
