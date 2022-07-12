from typing import Callable, Optional, TypeVar

import sentry_sdk
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, ConnectionTimeout

from chafan_core.app.config import settings

T = TypeVar("T")


def execute_with_es(callable: Callable[[Elasticsearch], T]) -> Optional[T]:
    # TODO: handle exception in initialization
    endpoint: Optional[Elasticsearch] = None
    ret = None
    if settings.ES_ENDPOINT:
        if settings.ES_HTTP_USERNAME:
            endpoint = Elasticsearch(
                [settings.ES_ENDPOINT],
                http_auth=(settings.ES_HTTP_USERNAME, settings.ES_HTTP_PASSWORD),
            )
        else:
            endpoint = Elasticsearch([settings.ES_ENDPOINT])
    try:
        if endpoint is not None:
            ret = callable(endpoint)
    except (ConnectionTimeout, ConnectionError) as e:
        sentry_sdk.capture_exception(e)
    finally:
        if endpoint:
            endpoint.close()
    return ret
