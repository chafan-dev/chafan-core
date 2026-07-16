"""Per-request context: lazy DB + Redis + principal + materializer.

Target replacement for DataBroker session holder and the former CachedLayer
façade. Services and responders take a RequestContext (or DataBroker subclass).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from chafan_core.app.common import get_redis_cli
from chafan_core.db.session import SessionLocal

if TYPE_CHECKING:
    import redis
    from chafan_core.app import models, schemas
    from chafan_core.app.materialize import Materializer
    from chafan_core.app.schemas.answer import AnswerPreview

# User.id -> { User.uuid -> count }
WeightedMatrixType = Dict[int, Dict[str, int]]
UserContributions = List[Tuple[int, List[int]]]


class RequestContext:
    """Lazy db + redis + principal for one HTTP request (or background task)."""

    def __init__(self, principal_id: Optional[int] = None) -> None:
        self.principal_id = principal_id
        self._redis: Optional["redis.Redis"] = None
        self._db: Optional[Session] = None
        self._principal: Optional["models.User"] = None
        self._materializer: Optional["Materializer"] = None
        self._follow_follow_fanout: Optional[WeightedMatrixType] = None
        self._user_contributions_map: Dict[int, UserContributions] = {}
        # True once a service has explicitly committed the unit of work.
        self._committed: bool = False

    # Historical call sites used layer.broker for get_db(); keep an alias.
    @property
    def broker(self) -> "RequestContext":
        return self

    def get_redis(self) -> "redis.Redis":
        if self._redis is None:
            self._redis = get_redis_cli()
        return self._redis

    def get_db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def materializer(self) -> "Materializer":
        if self._materializer is None:
            from chafan_core.app.materialize import Materializer

            self._materializer = Materializer(self, self.principal_id)  # type: ignore[arg-type]
        return self._materializer

    def try_get_current_user(self) -> Optional["models.User"]:
        if self.principal_id is None:
            return None
        if self._principal is None:
            from chafan_core.app import crud

            self._principal = crud.user.get(self.get_db(), id=self.principal_id)
        return self._principal

    def get_current_user(self) -> "models.User":
        user = self.try_get_current_user()
        if user is None:
            raise RuntimeError("No principal on RequestContext")
        return user

    def get_current_active_user(self) -> "models.User":
        u = self.get_current_user()
        assert u.is_active
        return u

    def unwrapped_principal_id(self) -> int:
        if self.principal_id is None:
            raise RuntimeError("No principal_id on RequestContext")
        return self.principal_id

    def get_follow_follow_fanout(self) -> WeightedMatrixType:
        if self._follow_follow_fanout is None:
            from chafan_core.app.recs import matrices as recs_matrices

            self._follow_follow_fanout = recs_matrices.compute_follow_follow_fanout(
                self.get_db()
            )
        return self._follow_follow_fanout

    def get_user_contributions(self, user: "models.User") -> UserContributions:
        if user.id not in self._user_contributions_map:
            from chafan_core.app.recs import matrices as recs_matrices

            self._user_contributions_map[user.id] = (
                recs_matrices.compute_user_contributions(user)
            )
        return self._user_contributions_map[user.id]

    def preview_of_user(self, user: "models.User") -> "schemas.UserPreview":
        from chafan_core.app.services import people as people_service

        return people_service.preview_of_user(self, user)

    def preview_of_answer(self, answer: "models.Answer") -> Optional["AnswerPreview"]:
        return self.materializer.preview_of_answer(answer)

    def site_schema_from_orm(self, site: "models.Site") -> "schemas.Site":
        from chafan_core.app.services import sites as sites_service

        return sites_service.site_schema(self, site)

    def channel_schema_from_orm(self, channel: "models.Channel") -> "schemas.Channel":
        return self.materializer.channel_schema_from_orm(channel)

    def get_user_follows(self, followed: "models.User") -> "schemas.UserFollows":
        from chafan_core.app.services import people as people_service

        return people_service.get_user_follows(self, followed)

    def get_site_by_subdomain(self, subdomain: str):
        from chafan_core.app.services import sites as sites_service

        return sites_service.get_site_by_subdomain(self.get_db(), subdomain)

    def get_site_info(self, *, subdomain: str) -> Optional["schemas.Site"]:
        from chafan_core.app.services import sites as sites_service

        return sites_service.get_site_info(self, subdomain=subdomain)

    def update_notification(
        self,
        notif: "models.Notification",
        notif_in: "schemas.NotificationUpdate",
    ) -> None:
        from chafan_core.app import crud

        crud.notification.update(self.get_db(), db_obj=notif, obj_in=notif_in)

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
