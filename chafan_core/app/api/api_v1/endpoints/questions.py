import datetime
from typing import Any, List, Optional, Union

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder

from chafan_core.app import crud, models, schemas, view_counters
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import OperationType, client_ip, run_dramatiq_task
from chafan_core.app.endpoint_utils import get_site
from chafan_core.app.limiter import limiter
from chafan_core.app.materialize import check_user_in_site, user_in_site
from chafan_core.app.recs.ranking import rank_answers
from chafan_core.app.schemas.event import (
    EventInternal,
    InviteAnswerInternal,
    UpvoteQuestionInternal,
)
from chafan_core.app.task import postprocess_new_question, postprocess_updated_question
from chafan_core.utils.base import HTTPException_, filter_not_none

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

AnswersData = Union[List[schemas.AnswerPreview], List[schemas.AnswerPreviewForVisitor]]


def _get_answers(
    cached_layer: CachedLayer, question: models.Question
) -> List[schemas.AnswerPreview]:
    return sorted(
        filter_not_none(
            [
                cached_layer.materializer.preview_of_answer(answer)
                for answer in question.answers
            ]
        ),
        key=lambda a: a.upvotes_count,
    )


def _get_answers_for_visitor(
    cached_layer: CachedLayer, question: models.Question
) -> List[schemas.AnswerPreviewForVisitor]:
    return sorted(
        filter_not_none(
            [
                cached_layer.materializer.preview_of_answer_for_visitor(answer)
                for answer in question.answers[:10]
            ]
        ),
        key=lambda a: a.upvotes_count,
    )


def _get_question_data(
    cached_layer: CachedLayer, question: models.Question
) -> Union[schemas.Question, schemas.QuestionForVisitor]:
    # TODO removed the check for principle id 2025-07-23
    question_data = cached_layer.question_schema_from_orm(question)
    #    if cached_layer.principal_id is None:
    #        question_data = cached_layer.materializer.question_for_visitor_schema_from_orm(
    #            question
    #        )
    #    else:
    #        question_data = cached_layer.materializer.question_schema_from_orm(question)
    if question_data is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exists in the system.",
        )
    return question_data


@router.get(
    "/{uuid}", response_model=Union[schemas.Question, schemas.QuestionForVisitor]
)
@limiter.limit("60/minute")
def get_question(
    response: Response,
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    uuid: str,
) -> Any:
    """
    Get question in one of current_user's belonging sites.
    """
    question = cached_layer.get_question_by_uuid(uuid)
    if question.is_hidden:
        raise HTTPException_(
            status_code=403,
            detail="Not allowed to access this quesion",
        )
    return _get_question_data(cached_layer, question)


@router.post("/{uuid}/views/", response_model=schemas.GenericResponse)
async def bump_views_counter(
    *,
    uuid: str,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    _current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    question = cached_layer.get_question_model_http(uuid)
    if question is None:
        raise HTTPException_(
            status_code=404,
            detail="No such question",
        )
    assert isinstance(question, models.Question)
    await view_counters.add_view_async(cached_layer, "question", question.id)
    return schemas.GenericResponse()


@router.get(
    "/{uuid}/answers/",
    response_model=Union[
        List[schemas.AnswerPreview], List[schemas.AnswerPreviewForVisitor]
    ],
)
def get_question_answers(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    uuid: str,
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
) -> Any:
    """
    Get question's answers' previews.
    """
    question = cached_layer.get_question_model_http(uuid)
    if current_user_id is not None:
        check_user_in_site(
            cached_layer.get_db(),
            site=question.site,
            user_id=current_user_id,
            op_type=OperationType.ReadSite,
        )
        return _get_answers(cached_layer, question)
    else:
        if not question.site.public_readable:
            raise HTTPException_(
                status_code=400,
                detail="Unauthorized.",
            )
        return _get_answers_for_visitor(cached_layer, question)


@router.post("/", response_model=schemas.Question)
def create_question(
    request: Request,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    question_in: schemas.QuestionCreate,
) -> Any:
    """
    Create new question authored by the current user in one of the belonging sites.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    crud.audit_log.create_with_user(
        db,
        ipaddr=client_ip(request),
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
            detail="Insuffient coins.",
        )
    new_question = crud.question.create_with_author(
        db, obj_in=question_in, author_id=current_user.id
    )
    # Subscribed to the authored question automatically
    current_user = crud.user.subscribe_question(
        db, db_obj=current_user, question=new_question
    )
    run_dramatiq_task(postprocess_new_question, new_question.id)
    return cached_layer.question_schema_from_orm(new_question)


@router.put("/{uuid}", response_model=schemas.Question)
def update_question(
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    question_in: schemas.QuestionUpdate,
    current_user_id: int = Depends(deps.get_current_user_id),
) -> Any:
    """
    Update question in one of current_user's belonging sites as member.
    """
    db = cached_layer.get_db()
    crud.audit_log.create_with_user(
        db,
        ipaddr=client_ip(request),
        user_id=current_user_id,
        api="put question",
        request_info={"question_in": jsonable_encoder(question_in), "uuid": uuid},
    )

    question = crud.question.get_by_uuid(db, uuid=uuid)
    if question is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exists in the system.",
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
    run_dramatiq_task(postprocess_updated_question, new_question.id)
    return cached_layer.question_schema_from_orm(new_question)


@router.get("/{uuid}/archives/", response_model=List[schemas.QuestionArchive])
def get_question_archives(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    uuid: str,
) -> Any:
    db = cached_layer.get_db()
    question = crud.question.get_by_uuid(db, uuid=uuid)
    if question is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exists in the system.",
        )
    return [
        cached_layer.materializer.question_archive_schema_from_orm(a)
        for a in question.archives
    ]


@router.get("/{uuid}/upvotes/", response_model=schemas.QuestionUpvotes)
def get_question_upvotes(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    *,
    uuid: str,
) -> Any:
    return cached_layer.materializer.get_question_upvotes(
        cached_layer.get_question_model_http(uuid)
    )


@router.put("/{uuid}/hide", response_model=schemas.Question)
def hide_question(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    question = cached_layer.get_question_model_http(uuid)
    if (
        question.site.moderator_id != cached_layer.principal_id
        and question.author_id != cached_layer.principal_id
    ):
        raise HTTPException_(
            status_code=400,
            detail="Unauthorized.",
        )
    question = crud.question.update(
        cached_layer.get_db(), db_obj=question, obj_in={"is_hidden": True}
    )
    return cached_layer.materializer.question_schema_from_orm(question)


@router.post(
    "/{uuid}/invite-answer/{user_uuid}", response_model=schemas.GenericResponse
)
def invite_answer(
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    uuid: str,
    user_uuid: str,
) -> Any:
    question = cached_layer.get_question_model_http(uuid)
    check_user_in_site(
        cached_layer.get_db(),
        site=question.site,
        user_id=cached_layer.unwrapped_principal_id(),
        op_type=OperationType.ReadSite,
    )
    invited_user = crud.user.get_by_uuid(cached_layer.get_db(), uuid=user_uuid)
    if invited_user is None:
        raise HTTPException_(
            status_code=400,
            detail="The user doesn't exists in the system.",
        )
    if invited_user.id == cached_layer.unwrapped_principal_id():
        raise HTTPException_(
            status_code=400,
            detail="You can't invite yourself.",
        )
    check_user_in_site(
        cached_layer.get_db(),
        site=question.site,
        user_id=invited_user.id,
        op_type=OperationType.WriteSiteQuestion,
    )
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    crud.notification.create_with_content(
        cached_layer.broker,
        receiver_id=invited_user.id,
        event=EventInternal(
            created_at=utc_now,
            content=InviteAnswerInternal(
                subject_id=cached_layer.unwrapped_principal_id(),
                question_id=question.id,
                user_id=invited_user.id,
            ),
        ),
    )
    return schemas.GenericResponse()


@router.post("/{uuid}/upvotes/", response_model=schemas.QuestionUpvotes)
def upvote_question(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Upvote question as the current user.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    question = cached_layer.get_question_model_http(uuid)
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
                detail="Insuffient coins.",
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


@router.delete("/{uuid}/upvotes/", response_model=schemas.QuestionUpvotes)
def cancel_upvote_question(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Cancel upvote for question as the current user.
    """
    current_user = cached_layer.get_current_active_user()
    db = cached_layer.get_db()
    question = crud.question.get_by_uuid(db, uuid=uuid)
    if question is None:
        raise HTTPException_(
            status_code=400,
            detail="The question doesn't exists in the system.",
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


@router.get("/{uuid}/page", response_model=schemas.QuestionPage)
@limiter.limit("60/minute")
async def get_question_page(
    response: Response,
    request: Request,
    *,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    uuid: str,
) -> Any:
    current_user_id = cached_layer.principal_id
    question = cached_layer.get_question_by_uuid(uuid, current_user_id)
    if question is None:
        cached_layer.create_audit(
            api=f"get_question_page {uuid} retrieved None",
            request=request,
            user_id=current_user_id,
        )
        raise HTTPException_(status_code=404, detail="No such question")
    question_data = _get_question_data(cached_layer, question)
    flags = schemas.QuestionPageFlags()
    if cached_layer.principal_id:
        if question.author_id == cached_layer.principal_id:
            flags.editable = True
            flags.hideable = True
        if user_in_site(
            cached_layer.get_db(),
            site=question.site,
            user_id=cached_layer.principal_id,
            op_type=OperationType.WriteSiteQuestion,
        ):
            flags.editable = True
        if user_in_site(
            cached_layer.get_db(),
            site=question.site,
            user_id=cached_layer.principal_id,
            op_type=OperationType.WriteSiteAnswer,
        ):
            flags.answer_writable = True
        if user_in_site(
            cached_layer.get_db(),
            site=question.site,
            user_id=cached_layer.principal_id,
            op_type=OperationType.WriteSiteComment,
        ):
            flags.comment_writable = True
        if question.site.moderator_id == cached_layer.principal_id:
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
                cached_layer.answer_schema_from_orm(answer)
                for answer in rank_answers(
                    question.answers, principal_id=cached_layer.principal_id
                )
            ]
        ),
        answer_previews=filter_not_none(
            [
                cached_layer.preview_of_answer(answer)
                for answer in rank_answers(
                    question.answers, principal_id=cached_layer.principal_id
                )
            ]
        ),
        question_subscription=cached_layer.get_question_subscription(question),
        flags=flags,
    )
