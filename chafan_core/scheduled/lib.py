import datetime
import secrets
from typing import Dict, List, Mapping, Tuple

import sentry_sdk
from pydantic.tools import parse_obj_as
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.email_utils import send_notification_email
from chafan_core.app.materialize import Materializer
from chafan_core.app.model_utils import is_live_answer, is_live_article
from chafan_core.app.schemas.user import (
    UserEducationExperienceInternal,
    UserWorkExperienceInternal,
)
from chafan_core.app.task_utils import execute_with_broker, execute_with_db
from chafan_core.db.session import SessionLocal
from chafan_core.utils.base import EntityType, filter_not_none


def deliver_notifications(data_broker: DataBroker) -> None:
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
            m = Materializer(data_broker, user.id)
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


def compute_karma(user: models.User) -> Tuple[int, Mapping[int, int]]:
    """
    TODO: consider public edit etc. contributions in future?
    """
    karma = 0
    site_karmas = {}
    if user.work_experiences:
        karma += (
            min(
                len(
                    parse_obj_as(
                        List[UserWorkExperienceInternal], user.work_experiences
                    )
                ),
                5,
            )
            * 2
        )
    if user.education_experiences:
        karma += (
            min(
                len(
                    parse_obj_as(
                        List[UserEducationExperienceInternal],
                        user.education_experiences,
                    )
                ),
                5,
            )
            * 2
        )
    profile_karma_from = [
        user.full_name,
        user.github_username,
        user.github_username,
        user.twitter_username,
        user.linkedin_url,
        user.homepage_url,
        user.zhihu_url,
        user.avatar_url,
        user.gif_avatar_url,
        user.personal_introduction,
    ]
    for item in profile_karma_from:
        if item:
            karma += 2
    for a in user.answers:
        if is_live_answer(a):
            v = 10 + a.upvotes_count * 10
            karma += v
            if a.site_id not in site_karmas:
                site_karmas[a.site_id] = v
            else:
                site_karmas[a.site_id] += v

    for q in user.questions:
        v = 5 + q.upvotes_count * 10
        karma += v
        if q.site_id not in site_karmas:
            site_karmas[q.site_id] = v
        else:
            site_karmas[q.site_id] += v

    for s in user.submissions:
        if not s.is_hidden:
            v = 1 + s.upvotes_count * 2
            karma += v
            if s.site_id not in site_karmas:
                site_karmas[s.site_id] = v
            else:
                site_karmas[s.site_id] += v

    for article in user.articles:
        if is_live_article(article):
            v = 5 + article.upvotes_count * 10
            karma += v

    for c in user.comments:
        v = 2
        karma += v
        if c.site_id:
            if c.site_id not in site_karmas:
                site_karmas[c.site_id] = v
            else:
                site_karmas[c.site_id] += v

    return karma, site_karmas


def refresh_karmas() -> None:
    print("refresh_karmas", flush=True)

    def runnable(db: Session) -> None:
        for user in crud.user.get_all_active_users(db):
            total_karma, site_karmas = compute_karma(user)
            user.karma = total_karma
            for site_id, karma in site_karmas.items():
                profile = crud.profile.get_by_user_and_site(
                    db, owner_id=user.id, site_id=site_id
                )
                if profile is not None:
                    profile.karma = karma

    execute_with_db(SessionLocal(), runnable)


def cache_matrices() -> None:
    def f(broker: DataBroker) -> None:
        l = CachedLayer(broker)
        l.get_follow_follow_fanout()
        for t in EntityType._member_map_.values():
            l.get_entity_similarity_matrix(t)  # type: ignore
        for u in crud.user.get_all_active_users(l.get_db()):
            l.get_user_contributions(u)

    execute_with_broker(f, use_read_replica=True)
