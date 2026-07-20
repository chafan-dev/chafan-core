from fastapi import APIRouter, Depends, Response

from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import rss as rss_service

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/site/{subdomain}/rss.xml")
def get_site_activity(
        *, response: Response,
        ctx: RequestContext = Depends(deps.get_request_context), subdomain: str
) -> str:
    """Get a site's activity. Pilot: RequestContext dependency."""
    logger.info("Generating RSS for site " + subdomain)
    rss_str = rss_service.site_rss_xml(ctx, subdomain=subdomain)
    return Response(content=rss_str, media_type="application/rss+xml")
