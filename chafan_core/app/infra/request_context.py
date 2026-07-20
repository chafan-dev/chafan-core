"""Per-request context: lazy DB + Redis + principal + PrincipalView shaper.

Constructed per-request by deps.py and for background work. Services and
responders take a RequestContext.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from chafan_core.app.common import get_redis_cli
from chafan_core.db.session import SessionLocal

if TYPE_CHECKING:
    import redis
    from chafan_core.app import models, schemas
    from chafan_core.app.infra.principal_view import PrincipalView
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
        self._principal_view: Optional["PrincipalView"] = None
        self._follow_follow_fanout: Optional[WeightedMatrixType] = None
        self._user_contributions_map: Dict[int, UserContributions] = {}
        # True once a service has explicitly committed the unit of work.
        self._committed: bool = False

    # Historical call sites used layer.broker for get_db(); keep an alias.
    @property
    def broker(self) -> "RequestContext":
        return self

    @property
    def redis(self) -> Optional["redis.Redis"]:
        return self._redis

    @redis.setter
    def redis(self, value: Optional["redis.Redis"]) -> None:
        self._redis = value

    @property
    def db(self) -> Optional[Session]:
        return self._db

    @db.setter
    def db(self, value: Optional[Session]) -> None:
        self._db = value

    def get_redis(self) -> "redis.Redis":
        if self._redis is None:
            self._redis = get_redis_cli()
        return self._redis

    def get_db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def principal_view(self) -> "PrincipalView":
        """PrincipalView for this request's principal (plain nested previews)."""
        if self._principal_view is None:
            from chafan_core.app.infra.principal_view import PrincipalView

            self._principal_view = PrincipalView(self, self.principal_id)
        return self._principal_view

    def as_principal(self, principal_id: Optional[int]) -> "PrincipalView":
        """Schema shaper for a different principal (feed, notifications, payments).

        Shares this context's db/redis. Reuses .principal_view when principal_id
        matches the request principal.
        """
        if principal_id == self.principal_id:
            return self.principal_view
        from chafan_core.app.infra.principal_view import PrincipalView

        return PrincipalView(self, principal_id)

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
        return self.principal_view.preview_of_answer(answer)

    def site_schema_from_orm(self, site: "models.Site") -> "schemas.Site":
        from chafan_core.app.services import sites as sites_service

        return sites_service.site_schema(self, site)

    def channel_schema_from_orm(self, channel: "models.Channel") -> "schemas.Channel":
        return self.principal_view.channel_schema_from_orm(channel)

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

    def commit(self) -> None:
        """Commit the unit of work (service or request boundary)."""
        if self._db is not None:
            self._db.commit()
            self._committed = True

    def rollback(self) -> None:
        if self._db is not None:
            self._db.rollback()
            self._committed = False

    def close(self) -> None:
        """Close the session. Callers must commit or rollback first on success/error."""
        if self._db is not None:
            if not self._committed:
                self._db.rollback()
            self._db.close()
            self._db = None
