"""Legacy session holder.

Prefer RequestContext (chafan_core.app.infra.request_context). DataBroker remains
as a thin compatibility wrapper used by CachedLayer and existing call sites.
use_read_replica is ignored (D6: single Postgres, no replica).
"""

from typing import Optional

import redis
from sqlalchemy.orm import Session

from chafan_core.app.infra.request_context import RequestContext
from chafan_core.db.session import SessionLocal


class DataBroker(RequestContext):
    """Backward-compatible alias: same lazy db/redis as RequestContext.

    close() still commits (legacy request-end behavior) so existing endpoints
    keep working until services own transactions.
    """

    def __init__(self, use_read_replica: bool = False) -> None:
        super().__init__(principal_id=None)
        # Kept for signature compatibility; ReadSessionLocal is an alias of SessionLocal.
        self.use_read_replica = use_read_replica

    # Expose redis/db attributes some call sites still poke at.
    @property
    def redis(self) -> Optional[redis.Redis]:
        return self._redis

    @redis.setter
    def redis(self, value: Optional[redis.Redis]) -> None:
        self._redis = value

    @property
    def db(self) -> Optional[Session]:
        return self._db

    @db.setter
    def db(self, value: Optional[Session]) -> None:
        self._db = value

    def get_db(self) -> Session:
        if self._db is None:
            # Ignore use_read_replica (D6).
            self._db = SessionLocal()
        return self._db

    def close(self) -> None:
        self.close_legacy_commit()
