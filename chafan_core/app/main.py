from typing import Any, MutableMapping, Optional

from dotenv import load_dotenv  # isort:skip

load_dotenv()  # isort:skip

import logging

import sentry_sdk
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

app = FastAPI(title=settings.PROJECT_NAME, **args)  # type: ignore

# Create a logger object
logger = logging.getLogger(__name__)

# Configure the logger to log level of INFO or higher
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

if enable_rate_limit():
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> Any:
    request_str = f"request.url: {request.url}\nrequest.method: {request.method}"
    err_msg = f"Validation error:\n{request_str}\nexc: {exc}\nexc.body: {exc.body}"
    if is_dev():
        # NOTE: need to print in order to capture by pytest
        print(err_msg)
    else:
        sentry_sdk.capture_message(err_msg)
    return await request_validation_exception_handler(request, exc)

def set_backend_cors_origins():
    origins = []
    if settings.DEBUG_BYPASS_BACKEND_CORS == 'magic':
        origins.append('*')
    for host in settings.CHAFAN_BACKEND_CORS_ORIGINS.split(','):
        origins.append(host)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

set_backend_cors_origins()

app.include_router(health.router)
app.include_router(api_router, prefix=settings.API_V1_STR)


# log settings
def log_settings() -> None:
    logger.info("settings:")
    for k, v in settings.__dict__.items():
        if not k.startswith("__"):
            logger.info(f"{k}: {v}")


log_settings()
