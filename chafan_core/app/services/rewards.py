"""Reward domain service."""

from __future__ import annotations

import datetime
from typing import List

from pydantic.tools import parse_obj_as

from chafan_core.app import crud, rep_manager, schemas
from chafan_core.app.common import OperationType
from chafan_core.app.materialize import can_read_answer
from chafan_core.app.responders import misc as misc_responder
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
from chafan_core.app.user_permission import user_in_site
from chafan_core.utils.base import HTTPException_


def list_rewards(ctx) -> List[schemas.Reward]:
    current_user = ctx.get_current_active_user()
    received = current_user.incoming_rewards
    given = current_user.outgoing_rewards
    rewards = sorted(received + given, key=lambda r: r.created_at, reverse=True)
    mat = ctx.materializer
    return [misc_responder.reward_schema_from_orm(mat, r) for r in rewards]


def create_reward(ctx, *, reward_in: RewardCreate) -> schemas.Reward:
    db = ctx.get_db()
    current_user = ctx.get_current_active_user()
    receiver = crud.user.get_by_uuid(db, uuid=reward_in.receiver_uuid)
    if receiver is None:
        raise HTTPException_(
            status_code=400,
            detail="The receiver doesn't exist in the system.",
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
    reward_event = None
    if reward_in.condition:
        if isinstance(reward_in.condition.content, AnsweredQuestionCondition):
            reward_event = CreateAnswerQuestionRewardInternal(
                subject_id=current_user.id,
                reward_id=reward.id,
            )
    if reward_event is not None:
        crud.notification.create_with_content(
            ctx,
            receiver_id=receiver.id,
            event=EventInternal(
                created_at=reward.created_at,
                content=reward_event,
            ),
        )
    return misc_responder.reward_schema_from_orm(ctx.materializer, reward)


def claim_reward(ctx, *, reward_id: int) -> schemas.Reward:
    db = ctx.get_db()
    reward = crud.reward.get(db, id=reward_id)
    current_user = ctx.get_current_active_user()
    if reward is None:
        raise HTTPException_(
            status_code=400,
            detail="The reward doesn't exist in the system.",
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
    rep_manager.award_coins(db, current_user, reward.coin_amount, "reward_claim")
    db.add(reward)
    db.commit()
    db.refresh(reward)
    reward_data = misc_responder.reward_schema_from_orm(ctx.materializer, reward)
    reward_event = None
    if reward_data.condition:
        if isinstance(reward_data.condition.content, AnsweredQuestionCondition):
            reward_event = ClaimAnswerQuestionRewardInternal(
                subject_id=current_user.id,
                reward_id=reward.id,
            )
    if reward_event is not None:
        crud.notification.create_with_content(
            ctx,
            receiver_id=reward.giver.id,
            event=EventInternal(
                created_at=utc_now,
                content=reward_event,
            ),
        )
    return reward_data


def refund_reward(ctx, *, reward_id: int) -> schemas.Reward:
    db = ctx.get_db()
    current_user = ctx.get_current_active_user()
    reward = crud.reward.get(db, id=reward_id)
    if reward is None:
        raise HTTPException_(
            status_code=400,
            detail="The reward doesn't exist in the system.",
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
    rep_manager.award_coins(db, current_user, reward.coin_amount, "reward_refund")
    db.add(reward)
    db.commit()
    db.refresh(reward)
    return misc_responder.reward_schema_from_orm(ctx.materializer, reward)
