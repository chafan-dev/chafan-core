from pydantic import BaseModel


class BotLinkCode(BaseModel):
    """What the website shows the user to carry to the bot."""

    code: str
    expires_in_seconds: int


class BotClaimLink(BaseModel):
    """What a bot sends to redeem a code the user handed it.

    `secret` identifies the bot. It authorises this one exchange and nothing
    else: it cannot start a link, and without a code it can do nothing at all.
    """

    secret: str
    code: str
