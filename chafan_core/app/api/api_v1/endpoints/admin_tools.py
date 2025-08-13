
from fastapi import APIRouter, Depends, Response

from chafan_core.app.config import settings
from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.feed import get_site_activities
from chafan_core.utils.base import HTTPException_
from chafan_core.app.responders.rss import build_rss

import logging
logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/full_site_activity/{passcode}/rss.xml")
async def get_site_activity(
        *, response: Response,
        cached_layer: CachedLayer = Depends(deps.get_cached_layer),
        passcode: str
) -> str:
    """
    Get full cha.fan activity.
    """
    logger.info("Generating RSS for all sites")
    code = settings.DEBUG_ADMIN_TOOL_FULL_SITE_PASSCODE
    if code is None or code == "" or code != passcode:
        raise HTTPException_(status_code=405, detail="Not allowed ")
    activities = await get_site_activities(cached_layer, None, settings.LIMIT_RSS_ADMIN_TOOL_FULL_SITE_ITEMS, True)
    rss_str = build_rss(activities, site=None)
    return Response(content=rss_str, media_type="application/rss+xml")


