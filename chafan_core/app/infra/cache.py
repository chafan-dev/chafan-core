"""Ephemeral Redis helpers (not a content-cache layer).

Keys kept here are short-lived operational state: view-bump queue, daily
invitation link id. Verification codes live in security.py already.
"""

from __future__ import annotations

import datetime
import json
from typing import Any, Callable, Optional, TypeVar

import redis
from fastapi.encoders import jsonable_encoder
from pydantic import TypeAdapter

from chafan_core.app.common import get_redis_cli

BUMP_VIEW_COUNT_QUEUE_CACHE_KEY = "chafan:bump-view-count"
DAILY_INVITATION_LINK_ID_CACHE_KEY = "chafan:daily-invitation-link-id"

T = TypeVar("T")


def get_redis() -> redis.Redis:
    return get_redis_cli()


def bump_view(object_type: str, obj_id: int, redis_cli: Optional[redis.Redis] = None) -> None:
    cli = redis_cli if redis_cli is not None else get_redis()
    cli.rpush(BUMP_VIEW_COUNT_QUEUE_CACHE_KEY, f"{object_type}:{obj_id}")


def get_or_set(
    *,
    key: str,
    type_: Any,
    fetch: Callable[[], T],
    ttl_hours: int,
    redis_cli: Optional[redis.Redis] = None,
) -> T:
    """Minimal get-or-set for the few remaining ephemeral payloads."""
    cli = redis_cli if redis_cli is not None else get_redis()
    value = cli.get(key)
    if value is not None:
        return TypeAdapter(type_).validate_json(value)
    data = fetch()
    if data is not None:
        cli.set(
            key,
            json.dumps(jsonable_encoder(data)),
            ex=datetime.timedelta(hours=ttl_hours),
        )
    return data
