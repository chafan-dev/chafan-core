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


def _build_rss(activities: List, site)->str:
    fg = FeedGenerator()
    fg.title("ChaFan RSS " + site.name)
    fg.description("Chafan RSS 圈子 " + site.name)
    fg.link(href=f"{settings.SERVER_HOST}/sites/{site.subdomain}")
    fg.id("https://cha.fan/")

    for ac in activities:
        fe = fg.add_entry()
        verb = "内容"
        user = ac.author.full_name
        if user is None or user == "":
            user ="茶饭用户"
        link = "https://cha.fan"
        description = "内容"

        if isinstance(ac, Answer):
            description = ac.body
            verb = "回答"
            answer = ac
            question = ac.question
            link = f"{settings.SERVER_HOST}/questions/{question.uuid}/answers/{answer.uuid}"
        if isinstance(ac, Question):
            description = ac.title
            verb = "提问"
            question = ac
            link = f"{settings.SERVER_HOST}/questions/{question.uuid}"

        title = f"{user} 发表了{verb}"
        fe.title(title)
        fe.link(href=link)
        fe.id(link)
        fe.description(description)
        fe.author(name=user)
        fe.pubDate(ac.updated_at)
    result = fg.rss_str(pretty=True)
    return result


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


