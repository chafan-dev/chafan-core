"""Feed / activity service."""

from __future__ import annotations

import logging
from typing import List, Optional

from chafan_core.app import schemas
from chafan_core.app.services import feed_fill
from chafan_core.app.services.feed_impl import get_activities_v2

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

    if subject_user_uuid is not None:
        # A profile timeline is a record of what one user did. Padding it with
        # somebody else's activity would make it say something untrue, so a
        # short one stays short.
        return activities

    return feed_fill.top_up(
        ctx,
        activities,
        receiver_id=current_user_id,
        limit=limit,
        before_activity_id=before_activity_id,
        random=random,
    )
