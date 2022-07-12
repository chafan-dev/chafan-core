import base64
import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Union

from elasticsearch.client import Elasticsearch
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from chafan_core.app import schemas
from chafan_core.app.common import client_ip
from chafan_core.app.config import settings
from chafan_core.app.es import execute_with_es
from chafan_core.utils.base import get_utc_now

ResponseModels = Union[schemas.QuestionPage, schemas.FeedSequence]


class APIID(str, Enum):
    question_page = "/questions/page"
    activities = "/activities"


class APIEvent(BaseModel):
    api_id: APIID
    session_id: str
    created_at: datetime.datetime
    method: str
    path: str
    request: Mapping[str, Any]
    response_base64: bytes


def get_session_id(user_id: Optional[int], request: Request) -> str:
    if user_id:
        return f"u_{user_id}"
    return f"ip_{client_ip(request)}"


async def log_event(
    *,
    user_id: Optional[int],
    api_id: APIID,
    request: Request,
    request_info: Mapping[str, Any],
    response: ResponseModels,
) -> None:
    event = APIEvent(
        api_id=api_id,
        session_id=get_session_id(user_id, request),
        created_at=get_utc_now(),
        method=request.method,
        path=request.url.path,
        request=request_info,
        response_base64=base64.b64encode(str.encode(response.json())),
    )

    def f(es: Elasticsearch) -> None:
        es.index(
            index=f"chafan.{settings.ENV}.api_event",
            doc_type="_doc",
            document={"doc": jsonable_encoder(event)},
        )

    execute_with_es(f)
