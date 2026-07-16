"""Per-request context: lazy DB + Redis + principal.

This is the target replacement for DataBroker and the rump of CachedLayer
(principal + sessions). Services and responders should take a RequestContext
instead of reaching into CachedLayer for sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from chafan_core.app.common import get_redis_cli
from chafan_core.db.session import SessionLocal

if TYPE_CHECKING:
    import redis
    from chafan_core.app import models


class RequestContext:
    """Lazy db + redis + principal for one HTTP request (or background task)."""

    def __init__(self, principal_id: Optional[int] = None) -> None:
        self.principal_id = principal_id
        self._redis: Optional["redis.Redis"] = None
        self._db: Optional[Session] = None
        self._principal: Optional["models.User"] = None
        # True once a service has explicitly committed the unit of work.
        self._committed: bool = False

    def get_redis(self) -> "redis.Redis":
        if self._redis is None:
            self._redis = get_redis_cli()
        return self._redis

    def get_db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def try_get_current_user(self) -> Optional["models.User"]:
        if self.principal_id is None:
            return None
        if self._principal is None:
            # Lazy import avoids circular import (crud → DataBroker → RequestContext).
            from chafan_core.app import crud

            self._principal = crud.user.get(self.get_db(), id=self.principal_id)
        return self._principal

    def get_current_user(self) -> "models.User":
        user = self.try_get_current_user()
        if user is None:
            raise RuntimeError("No principal on RequestContext")
        return user

    def mark_committed(self) -> None:
        """Call after an explicit service-level commit."""
        self._committed = True

    def close(self) -> None:
        """End of request: roll back unless a service marked committed."""
        if self._db is not None:
            if not self._committed:
                self._db.rollback()
            self._db.close()
            self._db = None

    def close_legacy_commit(self) -> None:
        """Match historical DataBroker.close(): commit write session then close.

        Used while endpoints still rely on request-end implicit commits.
        Remove once services own all transaction boundaries.
        """
        if self._db is not None:
            self._db.commit()
            self._db.close()
            self._db = None
