"""Transitional façade over RequestContext + materializer.

Prefer RequestContext for sessions/principal and services/ for domain logic.
Kept only while responders and a few call sites still expect this duck type.
"""

from typing import List, Optional

import redis
from sqlalchemy.orm.session import Session

from chafan_core.app import crud, models, schemas
from chafan_core.app.data_broker import DataBroker
from chafan_core.app import services
from chafan_core.app.schemas.answer import AnswerPreview
from chafan_core.utils.base import unwrap

import logging
logger = logging.getLogger(__name__)


class CachedLayer(object):
    """Thin adapter: principal + db/redis/materializer from broker RequestContext."""

    def __init__(self, broker: DataBroker, principal_id: Optional[int] = None) -> None:
        if principal_id is not None:
            broker.principal_id = principal_id
        elif broker.principal_id is not None:
            principal_id = broker.principal_id
        self.broker = broker
        self.principal_id = principal_id
        # Share request-scoped materializer / principal cache with the context.
        self._principal: Optional[models.User] = None

    @property
    def materializer(self):
        return self.broker.materializer

    def get_redis(self) -> redis.Redis:
        return self.broker.get_redis()

    def get_db(self) -> Session:
        return self.broker.get_db()

    def get_current_user(self) -> models.User:
        return unwrap(self.try_get_current_user())

    def try_get_current_user(self) -> Optional[models.User]:
        if self._principal:
            return self._principal
        user = self.broker.try_get_current_user()
        if user is not None:
            self._principal = user
            return user
        if not self.principal_id:
            return None
        self._principal = crud.user.get(self.get_db(), id=self.principal_id)
        return self._principal

    def get_current_active_user(self) -> models.User:
        u = self.get_current_user()
        assert u.is_active
        return u

    def unwrapped_principal_id(self) -> int:
        return unwrap(self.principal_id)

    def preview_of_user(self, user: models.User) -> schemas.UserPreview:
        return services.people.preview_of_user(self, user)

    def preview_of_answer(self, answer: models.Answer) -> Optional[AnswerPreview]:
        return self.materializer.preview_of_answer(answer)

    def site_schema_from_orm(self, site: models.Site) -> schemas.Site:
        return services.sites.site_schema(self, site)

    def channel_schema_from_orm(self, channel: models.Channel) -> schemas.Channel:
        return self.materializer.channel_schema_from_orm(channel)

    def get_follow_follow_fanout(self):
        return self.broker.get_follow_follow_fanout()

    def get_user_follows(self, followed: models.User) -> schemas.UserFollows:
        return services.people.get_user_follows(self, followed)

    def get_user_contributions(self, user: models.User):
        return self.broker.get_user_contributions(user)

    def get_site_by_subdomain(self, subdomain: str):
        return services.sites.get_site_by_subdomain(self.get_db(), subdomain)

    def get_site_info(self, *, subdomain: str) -> Optional[schemas.Site]:
        return services.sites.get_site_info(self, subdomain=subdomain)

    def update_notification(
        self,
        notif: models.Notification,
        notif_in: schemas.NotificationUpdate,
    ) -> None:
        crud.notification.update(self.get_db(), db_obj=notif, obj_in=notif_in)
