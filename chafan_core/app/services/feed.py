"""Feed / activity service."""

from __future__ import annotations

from typing import List, Optional

from chafan_core.app import schemas
from chafan_core.app.services.feed_impl import get_activities_v2, get_random_activities

import logging

logger = logging.getLogger(__name__)


def get_user_activity(
    ctx,
    *,
    current_user_id: int,
    before_activity_id: Optional[int],
    limit: int,
    random: bool,
    subject_user_uuid: Optional[str],
) -> List[schemas.Activity]:
    logger.info(f"services.feed get_user_activity for {current_user_id}")
    activities = get_activities_v2(
        ctx=ctx,
        before_activity_id=before_activity_id,
        limit=limit,
        receiver_user_id=current_user_id,
        subject_user_uuid=subject_user_uuid,
    )

    insufficient = limit - len(activities)
    tolerate_order = before_activity_id is None
    if random:
        tolerate_order = True

    if tolerate_order and insufficient > 0 and subject_user_uuid is None:
        extra_activities = get_random_activities(
            receiver_user_id=current_user_id,
            before_activity_id=before_activity_id,
            limit=limit,
        )
        activities.extend(extra_activities)

    return activities
