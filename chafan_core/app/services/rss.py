"""RSS feed building service."""

from __future__ import annotations

from chafan_core.app.config import settings
from chafan_core.app.responders.rss import build_rss
from chafan_core.app.services.feed_impl import get_site_activities
from chafan_core.utils.base import HTTPException_


def site_rss_xml(ctx, *, subdomain: str) -> str:
    site = ctx.get_site_by_subdomain(subdomain)
    if site is None:
        raise HTTPException_(status_code=404, detail="No such site " + subdomain)
    if not site.public_readable:
        raise HTTPException_(status_code=405, detail="Not allowed " + subdomain)
    activities = get_site_activities(ctx, site, settings.LIMIT_RSS_RESPONSE_ITEMS)
    return build_rss(activities, site)


def full_site_rss_xml(ctx, *, passcode: str) -> str:
    code = settings.DEBUG_ADMIN_TOOL_FULL_SITE_PASSCODE
    if code is None or code == "" or code != passcode:
        raise HTTPException_(status_code=405, detail="Not allowed ")
    activities = get_site_activities(
        ctx, None, settings.LIMIT_RSS_ADMIN_TOOL_FULL_SITE_ITEMS, True
    )
    return build_rss(activities, site=None)
