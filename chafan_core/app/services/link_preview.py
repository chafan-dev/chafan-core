"""Outbound link preview fetch (formerly CachedLayer.request_text)."""

from __future__ import annotations

from typing import Optional

import requests
import sentry_sdk


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
