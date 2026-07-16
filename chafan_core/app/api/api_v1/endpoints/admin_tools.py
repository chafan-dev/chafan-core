
from fastapi import APIRouter, Depends, Response

from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import rss as rss_service

import logging
logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/full_site_activity/{passcode}/rss.xml")
def get_site_activity(
        *, response: Response,
        ctx: RequestContext = Depends(deps.get_request_context),
        passcode: str
) -> str:
    """
    Get full cha.fan activity.
    """
    logger.info("Generating RSS for all sites")
    rss_str = rss_service.full_site_rss_xml(ctx, passcode=passcode)
    return Response(content=rss_str, media_type="application/rss+xml")
