import logging

from fastapi import APIRouter, Depends, Response

from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.config import settings
from chafan_core.app.feed import get_site_activities
from chafan_core.app.responders.rss import build_rss
from chafan_core.utils.base import HTTPException_

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/site/{subdomain}/rss.xml")
async def get_site_activity(
    *,
    response: Response,
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
    subdomain: str
) -> str:
    """
    Get a site's activity.
    """
    logger.info("Generating RSS for site " + subdomain)
    site = cached_layer.get_site_by_subdomain(subdomain)
    if site is None:
        raise HTTPException_(status_code=404, detail="No such site " + subdomain)
    if not site.public_readable:
        raise HTTPException_(status_code=405, detail="Not allowed " + subdomain)
    activities = await get_site_activities(
        cached_layer, site, settings.LIMIT_RSS_RESPONSE_ITEMS
    )
    logger.info("api get: " + str(activities))
    rss_str = build_rss(activities, site)
    return Response(content=rss_str, media_type="application/rss+xml")
