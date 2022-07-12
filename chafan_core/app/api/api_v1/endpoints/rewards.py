import datetime
from typing import Any, List

from fastapi import APIRouter, Depends
from pydantic.tools import parse_obj_as
from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import OperationType
from chafan_core.app.materialize import can_read_answer, user_in_site
from chafan_core.app.schemas.event import (
    ClaimAnswerQuestionRewardInternal,
    CreateAnswerQuestionRewardInternal,
    EventInternal,
)
from chafan_core.app.schemas.reward import (
    AnsweredQuestionCondition,
    RewardCondition,
    RewardCreate,
)
from chafan_core.utils.base import HTTPException_

router = APIRouter()


# FIXME: paging
@router.get("/", response_model=List[schemas.Reward])
def get_rewards(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
) -> Any:
    current_user = cached_layer.get_current_active_user()
    received = current_user.incoming_rewards
    given = current_user.outgoing_rewards
    rewards = sorted(received + given, key=lambda r: r.created_at, reverse=True)
    return [cached_layer.materializer.reward_schema_from_orm(r) for r in rewards]


@router.post("/", response_model=schemas.Reward)
def create_reward(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    reward_in: RewardCreate,
) -> Any:
    db = cached_layer.get_db()
    current_user = cached_layer.get_current_active_user()
    receiver = crud.user.get_by_uuid(db, uuid=reward_in.receiver_uuid)
    if receiver is None:
        raise HTTPException_(
            status_code=400,
            detail="The receiver doesn't exists in the system.",
        )
    if reward_in.condition:
        if isinstance(reward_in.condition.content, AnsweredQuestionCondition):
            question = crud.question.get_by_uuid(
                db, uuid=reward_in.condition.content.question_uuid
            )
            assert question is not None
            if not user_in_site(
                db,
                site=question.site,
                user_id=receiver.id,
                op_type=OperationType.WriteSiteAnswer,
            ):
                raise HTTPException_(
                    status_code=400,
                    detail="The receiver can't post answer for that question.",
                )
    if current_user.remaining_coins < reward_in.coin_amount:
        raise HTTPException_(
            status_code=400,
            detail="Insufficient coins.",
        )
    reward = crud.reward.create_with_giver(db, obj_in=reward_in, giver=current_user)
    # FIXME: reward event for other types of rewards (including non-conditonal ones)
    reward_event = None
    if reward_in.condition:
        if isinstance(reward_in.condition.content, AnsweredQuestionCondition):
            reward_event = CreateAnswerQuestionRewardInternal(
                subject_id=current_user.id,
                reward_id=reward.id,
            )
    if reward_event is not None:
        crud.notification.create_with_content(
            cached_layer.broker,
            receiver_id=receiver.id,
            event=EventInternal(
                created_at=reward.created_at,
                content=reward_event,
            ),
        )
    return cached_layer.materializer.reward_schema_from_orm(reward)


@router.post("/{id}/claim", response_model=schemas.Reward)
def claim_reward(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    id: int,
) -> Any:
    db = cached_layer.get_db()
    reward = crud.reward.get(db, id=id)
    current_user = cached_layer.get_current_active_user()
    if reward is None:
        raise HTTPException_(
            status_code=400,
            detail="The reward doesn't exists in the system.",
        )
    if reward.receiver_id != current_user.id:
        raise HTTPException_(
            status_code=400,
            detail="The reward is not for current user",
        )
    if reward.claimed_at is not None:
        raise HTTPException_(
            status_code=400,
            detail="The reward is already claimed",
        )
    if reward.refunded_at is not None:
        raise HTTPException_(
            status_code=400,
            detail="The reward is already refunded",
        )
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    if reward.expired_at < utc_now:
        raise HTTPException_(
            status_code=400,
            detail="The reward is already expired",
        )
    claimable = False
    if reward.condition is not None:
        condition = parse_obj_as(RewardCondition, reward.condition)
        if isinstance(condition.content, AnsweredQuestionCondition):
            question = crud.question.get_by_uuid(
                db, uuid=condition.content.question_uuid
            )
            assert question is not None
            claimable = any(
                can_read_answer(db, answer=answer, principal_id=reward.giver_id)
                for answer in question.answers
            )
    else:
        claimable = True
    if not claimable:
        raise HTTPException_(
            status_code=400,
            detail="The reward condition is not met yet",
        )
    reward.claimed_at = utc_now
    current_user.remaining_coins += reward.coin_amount
    db.add(current_user)
    db.add(reward)
    db.commit()
    db.refresh(reward)
    reward_data = cached_layer.materializer.reward_schema_from_orm(reward)
    reward_event = None
    if reward_data.condition:
        if isinstance(reward_data.condition.content, AnsweredQuestionCondition):
            reward_event = ClaimAnswerQuestionRewardInternal(
                subject_id=current_user.id,
                reward_id=reward.id,
            )
    if reward_event is not None:
        crud.notification.create_with_content(
            cached_layer.broker,
            receiver_id=reward.giver.id,
            event=EventInternal(
                created_at=utc_now,
                content=reward_event,
            ),
        )
    return reward_data


@router.post("/{id}/refund", response_model=schemas.Reward)
def refund_reward(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer_logged_in),
    *,
    db: Session = Depends(deps.get_db),
    id: int,
) -> Any:
    current_user = cached_layer.get_current_active_user()
    reward = crud.reward.get(db, id=id)
    if reward is None:
        raise HTTPException_(
            status_code=400,
            detail="The reward doesn't exists in the system.",
        )
    if reward.giver_id != current_user.id:
        raise HTTPException_(
            status_code=400,
            detail="The reward is not for current user",
        )
    if reward.claimed_at is not None:
        raise HTTPException_(
            status_code=400,
            detail="The reward is already claimed",
        )
    if reward.refunded_at is not None:
        raise HTTPException_(
            status_code=400,
            detail="The reward is already refunded",
        )
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    reward.refunded_at = utc_now
    current_user.remaining_coins += reward.coin_amount
    db.add(current_user)
    db.add(reward)
    db.commit()
    db.refresh(reward)
    return cached_layer.materializer.reward_schema_from_orm(reward)
