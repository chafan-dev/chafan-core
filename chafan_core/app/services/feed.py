"""Feed / activity service."""

from __future__ import annotations

import logging
from typing import List, Optional

from chafan_core.app import schemas
from chafan_core.app.services import feed_fill, feed_impl

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
    """The activities behind one GET /activities/ request.

    Two different questions reach this endpoint, and the branch below is where
    they part: a profile timeline asks what one user *did*, and the home feed
    asks what was *delivered* to the viewer.
    """
    logger.info(f"services.feed get_user_activity for {current_user_id}")

    if subject_user_uuid is not None:
        # Never padded. A profile is a record of what one user did, and filling
        # it out with somebody else's activity would make it say something
        # untrue.
        return feed_impl.subject_timeline(
            ctx,
            subject_user_uuid=subject_user_uuid,
            viewer_id=current_user_id,
            before_activity_id=before_activity_id,
            limit=limit,
        )

    activities = feed_impl.receiver_feed(
        ctx,
        receiver_id=current_user_id,
        before_activity_id=before_activity_id,
        limit=limit,
    )
    return feed_fill.top_up(
        ctx,
        activities,
        receiver_id=current_user_id,
        limit=limit,
        before_activity_id=before_activity_id,
        random=random,
    )
