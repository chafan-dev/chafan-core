"""Binding a bot session to a Chafan account, with a code the user carries.

The code travels **site -> bot**, never bot -> site, and that direction is the
whole security argument: whoever chooses the secret decides who gets bound.

Had the bot generated a key and put it in a URL, an attacker could start a link
on their own bot session and send the resulting link to someone else. The
victim clicks it while logged in, the backend mints a token for *their* account
under the *attacker's* key, and the attacker's session claims it. The browser
did exactly what it was asked, by the right user, on the right site; nothing in
the flow catches it. That is ordinary account-linking CSRF.

Sending the code the other way fixes it, because the code appears on the user's
own screen and only they can deliver it. The click proves the Chafan half; the
delivery proves the bot half. A one-directional flow only ever proves one.

It also keeps this module ignorant of what a bot is talking to. There is no
Discord identity here and no column for one: the platform-account -> token
mapping lives in the bot, which is what lets a second bot on another platform
reuse this endpoint with no change here at all.
"""

from __future__ import annotations

import datetime
import secrets
from typing import Optional

from chafan_core.app import crud, schemas, security
from chafan_core.app.config import settings
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.token import BOT_TOKEN_SRC_PREFIX
from chafan_core.app.services import tokens as tokens_service
from chafan_core.utils.base import HTTPException_

# Crockford-ish base32: no lowercase, and no 0/1/8/9 to be misread as O/I/B/g
# when someone copies the code off a screen by hand.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ2345679"
_CODE_LENGTH = 8


def _code_key(code: str) -> str:
    return f"chafan:bot-link-code:{code}"


def normalize_code(raw: str) -> str:
    """Accept what a person actually types.

    The code is shown as K4F2-9QTX, so the dash comes back about as often as
    not, along with stray spaces and the odd lowercase letter.
    """
    return "".join(c for c in raw.upper() if c.isalnum())


def format_code(code: str) -> str:
    """K4F29QTX -> K4F2-9QTX, which is what someone has to read and retype."""
    half = len(code) // 2
    return f"{code[:half]}-{code[half:]}"


def generate_link_code(ctx: RequestContext) -> schemas.BotLinkCode:
    """Issue a code for the logged-in user. **No token is minted here.**

    Minting on claim rather than on generate means an abandoned code never
    leaves a live token sitting in Redis waiting to leak. What is parked is an
    integer user id, which is worth nothing on its own.
    """
    user = ctx.get_current_active_user()
    code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
    ttl = datetime.timedelta(minutes=settings.BOT_LINK_CODE_EXPIRE_MINUTES)
    ctx.get_redis().set(_code_key(code), str(user.id), ex=ttl)
    return schemas.BotLinkCode(
        code=format_code(code),
        expires_in_seconds=int(ttl.total_seconds()),
    )


def _bot_for_secret(secret: str) -> Optional[str]:
    """Which bot this secret belongs to, compared in constant time.

    Every configured secret is compared even after a match, so the time taken
    does not reveal how far down the list the answer was.
    """
    found: Optional[str] = None
    for name, configured in settings.BOT_SECRETS.items():
        if secrets.compare_digest(secret, configured.get_secret_value()):
            found = name
    return found


def claim_link(ctx: RequestContext, *, data: schemas.BotClaimLink) -> schemas.Token:
    """Redeem a code for an access token for the user who generated it.

    This is the only endpoint a bot secret authorises. On its own the secret
    can do nothing: without a code that a logged-in user generated in the last
    few minutes and chose to hand over, there is nothing to redeem.
    """
    bot_name = _bot_for_secret(data.secret)
    if bot_name is None:
        raise HTTPException_(status_code=400, detail="Unauthenticated.")

    code = normalize_code(data.code)
    if not code:
        raise HTTPException_(status_code=400, detail="Invalid or expired code.")

    # Read and delete together: a code is single-use, and doing it in one step
    # means two bots racing on the same code cannot both be handed a token.
    user_id = ctx.get_redis().getdel(_code_key(code))
    if user_id is None:
        raise HTTPException_(status_code=400, detail="Invalid or expired code.")

    user = crud.user.get(ctx.get_db(), id=int(user_id))
    if user is None or not user.is_active:
        raise HTTPException_(status_code=400, detail="Invalid or expired code.")

    # Stamped with the versions as they stand now, so a later unlink refuses
    # this token, and with a src naming the bot, so the refusal can be aimed at
    # bot tokens alone.
    return schemas.Token(
        access_token=security.create_access_token(
            user.id,
            expires_delta=datetime.timedelta(
                minutes=settings.BOT_ACCESS_TOKEN_EXPIRE_MINUTES
            ),
            token_version=user.token_version or 0,
            bot_token_version=user.bot_token_version or 0,
            src=f"{BOT_TOKEN_SRC_PREFIX}{bot_name}",
        ),
        token_type="bearer",
    )


def revoke_my_bot_tokens(ctx: RequestContext) -> schemas.GenericResponse:
    """Refuse every bot token this user holds, leaving website sessions alone.

    Called by a bot on unlink, authenticated as the user with the very token it
    is giving up -- which is why it needs no secret and cannot revoke anyone
    else. It is idempotent in effect: a second call revokes an empty set.
    """
    user = ctx.get_current_active_user()
    tokens_service.revoke_bot_tokens(ctx.get_db(), user=user)
    return schemas.GenericResponse(success=True)
