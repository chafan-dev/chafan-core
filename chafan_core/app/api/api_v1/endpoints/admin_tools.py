import datetime
from typing import Any, Dict, List, Optional, Union

from feedgen.feed import FeedGenerator

from fastapi import APIRouter, Body, Depends, Request, Response, status
from fastapi.responses import PlainTextResponse

from fastapi.param_functions import Query
from pydantic.tools import parse_obj_as

from chafan_core.app.config import settings
from chafan_core.app.api import deps
from chafan_core.app.models import Answer, Question
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.feed import get_site_activities
from chafan_core.utils.base import HTTPException_


router = APIRouter()



import logging
logger = logging.getLogger(__name__)




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
    return ""
    site = cached_layer.get_site_by_subdomain(subdomain)
    if site is None:
        raise HTTPException_(status_code=404, detail="No such site " + subdomain)
    if not site.public_readable:
        raise HTTPException_(status_code=405, detail="Not allowed " + subdomain)
    activities = await get_site_activities(cached_layer, site, 100)
    logger.info("api get: " + str(activities))
    rss_str = _build_rss(activities, site)
    return Response(content=rss_str, media_type="application/rss+xml")


