from typing import Any, List

from fastapi import APIRouter, Depends

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.reward import RewardCreate
from chafan_core.app.services import rewards as rewards_service

router = APIRouter()


# FIXME: paging
@router.get("/", response_model=List[schemas.Reward])
def get_rewards(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return rewards_service.list_rewards(ctx)


@router.post("/", response_model=schemas.Reward)
def create_reward(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    reward_in: RewardCreate,
) -> Any:
    return rewards_service.create_reward(ctx, reward_in=reward_in)


@router.post("/{id}/claim", response_model=schemas.Reward)
def claim_reward(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    id: int,
) -> Any:
    return rewards_service.claim_reward(ctx, reward_id=id)


@router.post("/{id}/refund", response_model=schemas.Reward)
def refund_reward(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    id: int,
) -> Any:
    return rewards_service.refund_reward(ctx, reward_id=id)
