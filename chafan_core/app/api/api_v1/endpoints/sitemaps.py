from typing import Any

from fastapi import APIRouter, Depends

from chafan_core.app.api import deps
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.schemas.site import SiteMaps

router = APIRouter()


@router.get("/", response_model=SiteMaps)
def read_sitemaps(
    cached_layer: CachedLayer = Depends(deps.get_cached_layer),
) -> Any:
    """
    Retrieve site map.
    """
    return cached_layer.get_site_maps()
