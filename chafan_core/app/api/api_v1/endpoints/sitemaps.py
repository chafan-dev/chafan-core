from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.site import SiteMaps
from chafan_core.app.services import sites as sites_service

router = APIRouter()


@router.get("/", response_model=SiteMaps)
def read_sitemaps(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    """Retrieve site map. Pilot: Depends on RequestContext."""
    return sites_service.get_site_maps(ctx)
