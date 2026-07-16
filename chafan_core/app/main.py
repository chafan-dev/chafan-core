from typing import Any, MutableMapping, Optional

import logging
import logging.config
log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "app": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
} # https://betterstack.com/community/guides/logging/logging-with-fastapi/#configuring-your-logging-system
logging.config.dictConfig(log_config)
logger = logging.getLogger(__name__)


import uvicorn
import fastapi
import starlette
from fastapi import FastAPI
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from chafan_core.app.api import health
from chafan_core.app.api.api_v1.api import api_router
from chafan_core.app.common import enable_rate_limit, is_dev, report_msg
from chafan_core.app.config import settings
from chafan_core.app.infra.scheduler import set_up_scheduled_tasks
from chafan_core.app.limiter import limiter
from chafan_core.app.limiter_middleware import SlowAPIMiddleware


def _check_prod_safety() -> None:
    if settings.ENV != "prod":
        return
    if settings.DEBUG_BYPASS_BACKEND_CORS == "magic":
        raise RuntimeError("DEBUG_BYPASS_BACKEND_CORS='magic' is not allowed in prod")
    if settings.DEBUG_BYPASS_REDIS_VERIFICATION_CODE:
        raise RuntimeError("DEBUG_BYPASS_REDIS_VERIFICATION_CODE must be unset in prod")
    if settings.DEBUG_ADMIN_TOOL_FULL_SITE_PASSCODE == "5e5da072":
        raise RuntimeError("DEBUG_ADMIN_TOOL_FULL_SITE_PASSCODE must be changed from default in prod")


_check_prod_safety()


args: MutableMapping[str, Optional[Any]] = {}
if is_dev():
    args["openapi_url"] = f"{settings.API_V1_STR}/openapi.json"
else:
    args["openapi_url"] = None
    #args["docs_url"] = None
    args["redoc_url"] = None

app = FastAPI(title=settings.PROJECT_NAME, **args)  # type: ignore



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
    report_msg(err_msg)
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
    logger.info("Set CORS allowed origins: " + str(origins))

set_backend_cors_origins()

app.include_router(health.router)
app.include_router(api_router, prefix=settings.API_V1_STR)




def print_app_settings() -> None:
    logger.info("settings:")
    for k, v in settings.__dict__.items():
        if not k.startswith("__"):
            logger.info(f"{k}: {v}")

print_app_settings()
for lib in [fastapi, uvicorn, starlette]:
    logger.info("{} version: {}".format(lib.__name__, lib.__version__))

logger.info("Server launches")

@app.on_event("startup")
def _startup_scheduled_tasks() -> None:
    set_up_scheduled_tasks()


@app.on_event("shutdown")
def shutdown_event():
    logger.info("Stub: shutdown_event")

