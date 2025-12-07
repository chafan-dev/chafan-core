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


from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = BackgroundScheduler()
import sentry_sdk
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
from chafan_core.app.common import enable_rate_limit, is_dev
from chafan_core.app.config import settings
from chafan_core.app.limiter import limiter
from chafan_core.app.limiter_middleware import SlowAPIMiddleware
from chafan_core.app.task import (
        write_view_count_to_db,
        refresh_search_index,
)

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
def set_up_scheduled_tasks():
    if not scheduler.running:
        scheduler.add_job(
                write_view_count_to_db,
                trigger=IntervalTrigger(minutes=settings.SCHEDULED_TASK_UPDATE_VIEW_COUNT_MINUTES),
                name="write_new_activities_to_feeds")
        scheduler.add_job(
                refresh_search_index,
                trigger=IntervalTrigger(hours=settings.SCHEDULED_TASK_REFRESH_SEARCH_INDEX_HOURS),
                name="refresh_search_index")
        scheduler.start()
        logger.info("Set up scheduled tasks")
    else:
        logger.info("Scheduler already running, skipping scheduled task setup")


@app.on_event("shutdown")
def shutdown_event():
    logger.info("Stub: shutdown_event")

