from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.site import SiteMaps
from chafan_core.app.services import sites as sites_service

router = APIRouter()


@router.get("/", response_model=SiteMaps)
def read_sitemaps(
    ctx: RequestContext = Depends(deps.get_request_context),
) -> Any:
    """
    Retrieve site map.

    Pilot: Depends on RequestContext (DataBroker), not get_cached_layer.
    """
    # get_request_context yields DataBroker; thin CachedLayer only for site_schema.
    broker = ctx if isinstance(ctx, DataBroker) else DataBroker(principal_id=ctx.principal_id)
    layer = CachedLayer(broker, ctx.principal_id)
    return sites_service.get_site_maps(layer)
