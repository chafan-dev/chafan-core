"""Padding for a feed that came up nearly empty.

A new user follows nobody, so their feed has nothing in it and the home page
renders blank. This module puts *something* there. That is its entire job.

Deliberately a placeholder
--------------------------
There is no ranking here, no personalization, no notion of what is worth
reading -- just the most recent publicly-readable activity. Choosing good
content is a real design problem and is not attempted yet. When it is, this
module is the one thing that changes: everything else knows only
:func:`top_up`.

Best-effort, and bounded
------------------------
It looks at a fixed window of recent activity and returns what passes. Coming
back with fewer than asked -- or with nothing -- is a correct outcome, not a
failure to retry harder. That is what lets the query stay bounded, and bounded
is the point: the version this replaces queried the whole ``activity`` table
with no ``LIMIT`` and materialized rows until it had enough, so its cost grew
with the table on every under-filled request.

It also dropped the ``activity.id % 10 != receiver_id % 10`` filter that
version used. That was never randomizing anything -- it is deterministic, so a
user saw identical padding on every request and any two users in the same
bucket saw identical padding as each other. It only cost an unindexable scan.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Set

from chafan_core.app import models, schemas
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services.activity_policy import ALWAYS_PUBLIC_EVENT_VERBS
from chafan_core.app.services.feed_impl import materialize_activity

logger = logging.getLogger(__name__)

# Below this many real activities the page reads as empty and is worth padding.
# A guess, and the number to revisit when content quality gets designed. The
# version this replaces padded whenever the page was not completely full, so a
# user one item short of a full page triggered the whole scan described above.
FILL_BELOW = 5

# How far back to look. Caps both the query and the number of materializations,
# each of which costs several more queries. Padding that comes up short is
# fine; padding that walks the table is not.
SCAN_LIMIT = 200


def _is_public(activity: schemas.Activity) -> bool:
    """Whether this activity may be shown to someone with no connection to it.

    The per-viewer permission gate in ``materialize_activity`` has already run
    by the time this is called; this is the *additional* restriction that
    padding is public content only. A viewer's own private-site activity
    reaches them through the feed, never through padding.
    """
    if activity.site and activity.site.public_readable:
        return True
    return activity.event.content.verb in ALWAYS_PUBLIC_EVENT_VERBS


def _recent_public(
    ctx: RequestContext,
    *,
    receiver_id: int,
    count: int,
    exclude_activity_ids: Set[int],
    before_activity_id: Optional[int],
) -> List[schemas.Activity]:
    db = ctx.get_db()
    query = db.query(models.Activity)
    if before_activity_id is not None:
        query = query.filter(models.Activity.id < before_activity_id)
    recent = query.order_by(models.Activity.id.desc()).limit(SCAN_LIMIT).all()

    padding: List[schemas.Activity] = []
    for activity in recent:
        if activity.id in exclude_activity_ids:
            continue
        materialized = materialize_activity(ctx, activity, receiver_id, None)
        if materialized is None or not _is_public(materialized):
            continue
        padding.append(materialized)
        if len(padding) >= count:
            break
    return padding


def top_up(
    ctx: RequestContext,
    activities: List[schemas.Activity],
    *,
    receiver_id: int,
    limit: int,
    before_activity_id: Optional[int],
    random: bool,
) -> List[schemas.Activity]:
    """``activities``, padded with recent public activity if it is nearly empty.

    Never returns more than ``limit`` items, and never repeats an activity that
    is already in ``activities`` -- the version this replaces did both, because
    it asked for a full ``limit`` of padding regardless of how many real
    activities it already had and appended without checking for overlap.
    """
    if before_activity_id is not None and not random:
        # Later pages are not padded: the reader has already seen the top of
        # the feed, so a blank page there means the end of it.
        return activities
    if len(activities) >= FILL_BELOW:
        return activities
    shortfall = limit - len(activities)
    if shortfall <= 0:
        return activities

    padding = _recent_public(
        ctx,
        receiver_id=receiver_id,
        count=shortfall,
        exclude_activity_ids={a.id for a in activities},
        before_activity_id=before_activity_id,
    )
    logger.info(
        "padded a %d-item feed for user %s with %d recent public activities",
        len(activities),
        receiver_id,
        len(padding),
    )
    return activities + padding
