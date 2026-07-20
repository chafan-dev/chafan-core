import datetime
import logging
import secrets
from typing import Dict, List

import sentry_sdk
from sqlalchemy.orm import Session

from chafan_core.app import crud, models, rep_manager
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.email_utils import send_notification_email
from chafan_core.app.infra.runtime import execute_with_broker, execute_with_db
from chafan_core.db.session import SessionLocal
from chafan_core.utils.base import EntityType, filter_not_none

karma_drift_logger = logging.getLogger("chafan.karma_drift")


def deliver_notifications(data_broker: RequestContext) -> None:
    db = data_broker.get_db()
    print(f"Deliver notifications @ {datetime.datetime.now(tz=datetime.timezone.utc)}")
    user_notifications: Dict[models.User, List[models.Notification]] = {}
    for notif in crud.notification.get_undelivered_unread(db):
        if notif.receiver not in user_notifications:
            user_notifications[notif.receiver] = []
        user_notifications[notif.receiver].append(notif)
    for user, notifs in user_notifications.items():
        if not user.is_active:
            continue
        if not user.enable_deliver_unread_notifications:
            continue
        if user.unsubscribe_token is None:
            user.unsubscribe_token = secrets.token_urlsafe(10)
            db.commit()
        try:
            m = data_broker.as_principal(user.id)
            ns = filter_not_none([m.notification_schema_from_orm(n) for n in notifs])
            if ns:
                send_notification_email(
                    user.email,
                    notifications=ns,
                    unsubscribe_token=user.unsubscribe_token,
                )
        except Exception as e:
            sentry_sdk.capture_exception(e)
            break
        for notif in notifs:
            notif.is_delivered = True
    db.commit()


def refresh_karmas() -> None:
    print("refresh_karmas", flush=True)

    def runnable(db: Session) -> None:
        for user in crud.user.get_all_active_users(db):
            stored = user.karma or 0
            authoritative = rep_manager.compute_karma(db, user)
            drift = abs(authoritative - stored)
            if drift > 50:
                karma_drift_logger.error(
                    f"karma drift user_id={user.id} stored={stored} computed={authoritative} drift={drift}"
                )
            elif drift > 5:
                karma_drift_logger.warning(
                    f"karma drift user_id={user.id} stored={stored} computed={authoritative} drift={drift}"
                )
            rep_manager.set_karma(db, user, authoritative)

    execute_with_db(SessionLocal(), runnable)


def cache_matrices() -> None:
    """Warm recs matrices (in-process; content redis cache removed)."""

    def f(broker: RequestContext) -> None:
        from chafan_core.app.recs import matrices as recs_matrices

        db = broker.get_db()
        recs_matrices.compute_follow_follow_fanout(db)
        for t in EntityType._member_map_.values():
            recs_matrices.compute_entity_similarity_matrix(db, t)  # type: ignore
        for u in crud.user.get_all_active_users(db):
            recs_matrices.compute_user_contributions(u)

    execute_with_broker(f)
