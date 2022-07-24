from typing import Any, MutableMapping, Optional

import sentry_sdk
from elasticapm.contrib.starlette import ElasticAPM  # type: ignore
from elasticapm.contrib.starlette import make_apm_client
from fastapi import FastAPI
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from chafan_core.app.api import health
from chafan_core.app.api.api_v1.api import api_router
from chafan_core.app.common import enable_rate_limit, is_dev
from chafan_core.app.config import settings
from chafan_core.app.limiter import limiter
from chafan_core.app.limiter_middleware import SlowAPIMiddleware

args: MutableMapping[str, Optional[Any]] = {}
if is_dev():
    args["openapi_url"] = f"{settings.API_V1_STR}/openapi.json"
else:
    args["openapi_url"] = None
    args["docs_url"] = None
    args["redoc_url"] = None

app = FastAPI(title=settings.PROJECT_NAME, **args)
if enable_rate_limit():
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

if not is_dev() and settings.ES_APM_SECRET_TOKEN and settings.ES_APM_SERVER_URL:
    app.add_middleware(
        ElasticAPM,
        client=make_apm_client(
            {
                "SERVICE_NAME": f"chafan-api-{settings.ENV}",
                "SECRET_TOKEN": settings.ES_APM_SECRET_TOKEN,
                "SERVER_URL": settings.ES_APM_SERVER_URL,
            }
        ),
    )


@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> Any:
    req_json = None
    try:
        req_json = await request.json()
    except Exception:
        if is_dev():
            print("request parsing error")
    err_msg = f"Validation error:\n{request.url}\n{exc}\n{req_json}"
    if is_dev():
        print(err_msg)
    else:
        sentry_sdk.capture_message(err_msg)
    return await request_validation_exception_handler(request, exc)


# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    origins = settings.BACKEND_CORS_ORIGINS
    if settings.AWS_CLOUDFRONT_HOST:
        origins.append(settings.AWS_CLOUDFRONT_HOST)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health.router)
app.include_router(api_router, prefix=settings.API_V1_STR)

print(app.exception_handlers)
