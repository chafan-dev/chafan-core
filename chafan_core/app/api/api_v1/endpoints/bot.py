"""Endpoints a bot talks to. Two of them, and neither can act on its own.

Nothing here knows what Discord is. A bot identifies itself with its own secret
to redeem a code, and thereafter holds an ordinary per-user access token and
calls the ordinary API as that user -- which is why there is no /bot/ twin of
any write endpoint, and why adding a bot on another platform needs no change
here.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.limiter import limiter
from chafan_core.app.services import bot_links as bot_links_service

router = APIRouter()


@router.post("/claim-link/", response_model=schemas.Token)
# The bot secret should not be the only lock on this, but the limit has to be
# set against the right threat. Guessing is already hopeless: a code is 8
# characters from a 29-character alphabet, about 2^39, and lives ten minutes.
# No per-minute figure worth writing changes that.
#
# What a tight limit *would* break is legitimate use. This limiter is keyed on
# the client IP, and a bot is one IP for its entire community -- so every claim
# anyone makes shares this budget, and a low ceiling means the eleventh person
# to link on launch day is told to go away. 60/minute leaves guessing exactly as
# hopeless while giving a real linking burst room to land.
@limiter.limit("60/minute")
def claim_link(
    response: Response,
    request: Request,
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    data: schemas.BotClaimLink,
) -> Any:
    """Exchange a code the user generated on cha.fan for their access token."""
    return bot_links_service.claim_link(ctx, data=data)


@router.post("/revoke/", response_model=schemas.GenericResponse)
def revoke_bot_tokens(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    """Give up every bot token for the calling user.

    Authenticated as the user, with the token being surrendered, so it needs no
    secret and can revoke nobody else. Website sessions are not affected.
    """
    return bot_links_service.revoke_my_bot_tokens(ctx)
