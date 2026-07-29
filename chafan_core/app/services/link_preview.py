"""Link preview: the outbound fetch and the OpenGraph scrape over it."""

from __future__ import annotations

from typing import Dict, Optional
from urllib.parse import urlparse

import requests
import sentry_sdk
from parsel.selector import Selector

from chafan_core.utils.base import HTTPException_

_HOSTNAMES_FOR_LINK_PREVIEW = set(
    ["www.flickr.com", "github.com", "twitter.com", "www.zhihu.com"]
)


def request_text(url: str) -> Optional[str]:
    try:
        response = requests.get(
            url,
            timeout=1,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/90.0.4430.93 Safari/537.36"
                )
            },
        )
        if response.ok:
            return response.text
    except Exception as e:
        sentry_sdk.capture_exception(e)
    return None


def get_link_preview(url: str) -> Dict[str, str]:
    """OpenGraph properties (plus <title>) for one of a few allowed hosts."""
    parsed = urlparse(url)
    if parsed.hostname not in _HOSTNAMES_FOR_LINK_PREVIEW:
        raise HTTPException_(
            status_code=400,
            detail="Invalid hostname for link preview.",
        )
    response_text = request_text(url)
    if not response_text:
        raise HTTPException_(
            status_code=400,
            detail="Unavailable link preview.",
        )
    s = Selector(text=response_text)
    properties = {}
    for e in s.xpath("//meta"):
        if "property" in e.attrib and "content" in e.attrib:
            properties[e.attrib["property"]] = e.attrib["content"]
    title = s.xpath("//title/text()").extract_first()
    if title:
        properties["title"] = title
    return properties
