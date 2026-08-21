"""Token revocation: the negative record that makes stateless JWTs refusable.

Chafan's tokens are stateless JWTs, so storage cannot hold the *positive*
record of a live session -- there is nothing to look up. What it holds instead
is the reason to refuse: a counter per user, stamped into every token it mints,
and compared on the way back in.

Why the database rather than Redis alone. Losing a store of positive records
logs people out, which is safe. Losing a store of *negative* records finds no
reason to reject and accepts -- previously revoked tokens quietly work again,
at exactly the moment during incident recovery when Redis is most likely to
have been rebuilt. Fail-open is the wrong direction for a control reached for
during an incident, so the counters live on the user row and Redis is only a
cache in front of them.

Two counters, not one. token_version covers every token the user holds, which
is what a "log out everywhere" control would bump. bot_token_version covers
only tokens whose `src` names a bot, so unlinking a bot revokes the bot's
access without ending that person's website session -- which is what someone
running /chafan unlink means, and never "sign me out of cha.fan".
"""

from __future__ import annotations

import datetime
from typing import Tuple

from sqlalchemy import event
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.common import get_redis_cli
from chafan_core.db.session import SessionLocal

# A bump drops the cache entry as soon as its transaction commits, so
# revocation normally takes effect on the very next request rather than when
# some TTL lapses. The TTL is the backstop for the one race a read-through
# cache cannot close: a concurrent reader that missed, read the old row, and
# writes it back *after* the delete would otherwise pin the stale version for
# the whole TTL. A minute bounds that to a minute, and costs one indexed
# single-row read per active user per minute -- less than the request it rides
# along with already spends.
CACHE_TTL = datetime.timedelta(seconds=60)


def _cache_key(user_id: int) -> str:
    return f"chafan:token-versions:{user_id}"


def current_versions(user_id: int) -> Tuple[int, int]:
    """(token_version, bot_token_version) for this user.

    Both live in one cache entry, so the hot path is a single Redis GET -- the
    same round trip slowapi already makes per request for rate limiting -- with
    an indexed single-row read behind it on a miss.
    """
    redis_cli = get_redis_cli()
    cached = redis_cli.get(_cache_key(user_id))
    if cached is not None:
        versions = _parse(cached)
        if versions is not None:
            return versions

    db = SessionLocal()
    try:
        row = (
            db.query(models.User.token_version, models.User.bot_token_version)
            .filter(models.User.id == user_id)
            .first()
        )
    finally:
        db.close()

    # A token whose subject no longer exists is refused elsewhere, on the
    # lookup of the user itself. Zeroes here keep this function total.
    versions = (row[0] or 0, row[1] or 0) if row is not None else (0, 0)
    redis_cli.set(_cache_key(user_id), _format(versions), ex=CACHE_TTL)
    return versions


def revoke_bot_tokens(db: Session, *, user: models.User) -> int:
    """Refuse every bot token this user holds. Website sessions are untouched."""
    user.bot_token_version = (user.bot_token_version or 0) + 1
    db.add(user)
    _forget_on_commit(db, user.id)
    return user.bot_token_version


def revoke_all_tokens(db: Session, *, user: models.User) -> int:
    """Refuse every token this user holds, bot and browser alike."""
    user.token_version = (user.token_version or 0) + 1
    db.add(user)
    _forget_on_commit(db, user.id)
    return user.token_version


def _forget_on_commit(db: Session, user_id: int) -> None:
    """Drop the cached versions once the bump is durable, and not before.

    Not before, because a delete inside an open transaction opens a window as
    long as the transaction itself: a concurrent reader misses, reads the row
    as it still stands, and caches the *old* version. Waiting for the commit
    means the row a racing reader finds is already the new one.

    Nothing is scheduled if the transaction rolls back, which is correct --
    there is then no bump to publish.
    """

    @event.listens_for(db, "after_commit", once=True)
    def _drop(session: Session) -> None:
        get_redis_cli().delete(_cache_key(user_id))


def _forget(user_id: int) -> None:
    """Drop the cached versions now. For callers that own their transaction."""
    get_redis_cli().delete(_cache_key(user_id))


def _format(versions: Tuple[int, int]) -> str:
    return f"{versions[0]}:{versions[1]}"


def _parse(raw: str):
    parts = raw.split(":")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        # A malformed entry reads as a miss rather than as version zero, so a
        # corrupted cache cannot resurrect a revoked token.
        return None
