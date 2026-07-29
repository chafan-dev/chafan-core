"""The one-off welcome-test reward: pass the signup quiz, get coins.

Its own module rather than part of services/rewards.py, which owns the
answer-question Reward model; this pays a CoinDeposit and touches no Reward.
"""

from __future__ import annotations

from chafan_core.app import crud, schemas
from chafan_core.app.config import settings
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.coin_deposit import CoinDepositCreate, CoinDepositReference
from chafan_core.app.services import forms as forms_service
from chafan_core.utils.base import HTTPException_

PASS_RATIO = 0.6


# TODO Remove this. put this test in backend
def claim_welcome_test_rewards(
    ctx: RequestContext, *, form_response_id: int
) -> schemas.msg.ClaimWelcomeTestScoreMsg:
    current_user = ctx.get_current_active_user()
    db = ctx.get_db()
    if current_user.claimed_welcome_test_rewards_with_form_response_id is not None:
        raise HTTPException_(status_code=400, detail="Claimed.")
    form_response = crud.form_response.get(db, id=form_response_id)
    if form_response is None:
        raise HTTPException_(status_code=400, detail="Invalid form response id.")
    if form_response.form.uuid != settings.WELCOME_TEST_FORM_UUID:
        raise HTTPException_(status_code=400, detail="Wrong form.")
    if form_response.response_author_id != current_user.id:
        raise HTTPException_(status_code=400, detail="Unauthorized.")
    scores = forms_service.compute_score_of_form_response(form_response)
    if float(scores.score) < float(scores.full_score) * PASS_RATIO:
        return schemas.msg.ClaimWelcomeTestScoreMsg(
            success=False,
            scores=scores,
        )
    current_user.claimed_welcome_test_rewards_with_form_response_id = form_response_id
    crud.coin_deposit.make_deposit(
        db,
        obj_in=CoinDepositCreate(
            payee_id=current_user.id,
            amount=scores.score,
            ref_id=CoinDepositReference(
                action="welcome_test_rewards",
                object_id=str(current_user.id),
            ).json(),
            comment="",
        ),
        authorizer_id=current_user.id,
        payee=current_user,
    )
    db.add(current_user)
    return schemas.msg.ClaimWelcomeTestScoreMsg(
        success=True,
        scores=scores,
    )
