from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


# Where a token was minted. Anything starting "bot:" is a bot token and is
# additionally checked against the user's bot_token_version.
WEB_TOKEN_SRC = "web"
BOT_TOKEN_SRC_PREFIX = "bot:"


class TokenPayload(BaseModel):
    sub: Optional[int] = None
    # Every token issued before revocation shipped carries neither claim.
    # A missing `ver` must read as 0 -- the column default -- and a missing
    # `src` as web, or deploying this logs out every user on the site at once.
    ver: int = 0
    bver: int = 0
    src: str = WEB_TOKEN_SRC

    @property
    def is_bot_token(self) -> bool:
        return self.src.startswith(BOT_TOKEN_SRC_PREFIX)
