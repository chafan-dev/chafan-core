import re
from typing import Iterator, Literal, Optional, Tuple

import sentry_sdk
from pydantic import AnyHttpUrl, ValidationError
from pydantic.types import SecretStr
from pydantic_settings import BaseSettings
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from chafan_core.utils.validators import CaseInsensitiveEmailStr


class Settings(BaseSettings):
    ############ Common ############
    SERVER_HOST: str
    ENV: Literal["dev", "stag", "prod"] = "dev"
    DB_SESSION_POOL_SIZE: int = 60
    DB_SESSION_POOL_MAX_OVERFLOW_SIZE: int = 20
    DEFAULT_LOCALE: Literal["en", "zh"] = "zh"
    PROJECT_NAME: str = "Chafan Dev"
    SENTRY_DSN: Optional[AnyHttpUrl] = None

    DATABASE_URL: str
    REDIS_URL: str

    ENABLE_CAPTCHA: bool = False


    EMAILS_ENABLED: bool = False
    EMAIL_SMTP_HOST: Optional[str] = None
    EMAIL_SMTP_PORT: Optional[int] = None
    EMAIL_SMTP_LOGIN_USERNAME: Optional[str] = None
    EMAIL_SMTP_LOGIN_PASSWORD: Optional[str] = None
    EMAIL_TEMPLATES_DIR: str = "chafan_core/app/email-templates/build"


    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None

    # Image uploads, backed by an S3-compatible object store (Storm Buckets).
    # Deployment settings only: nothing in here decides a rule. The karma gate
    # and coin cost live in rules.py, the size cap in common.py.
    UPLOADS_S3_ENDPOINT_URL: Optional[str] = None  # from the Storm dashboard
    UPLOADS_S3_ACCESS_KEY_ID: Optional[str] = None
    UPLOADS_S3_SECRET_ACCESS_KEY: Optional[str] = None
    UPLOADS_S3_BUCKET: Optional[str] = None
    UPLOADS_S3_REGION: str = "auto"
    UPLOADS_PUBLIC_URL_BASE: Optional[str] = None  # https://uploads.cha.fan

    USERS_OPEN_REGISTRATION: bool = True

    ############ Web server only ############
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: Optional[str] = None
    # 60 minutes * 24 hours * 60 days = 60 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 60
    API_SERVER_SCHEME: str = "https"

    DEBUG_BYPASS_BACKEND_CORS: str = "false"
    # TODO Better default value - 2024 Oct
    CHAFAN_BACKEND_CORS_ORIGINS: str = "https://127.0.0.1:8080"

    HCAPTCHA_SITEKEY: str = "10000000-ffff-ffff-ffff-000000000001"
    HCAPTCHA_SECRET: str = "0x0000000000000000000000000000000000000000"

    WELCOME_TEST_FORM_UUID: str = "4CGv4iReMxuWjs3T2PEY"

    SEARCH_INDEX_FILESYSTEM_PATH: str = "/tmp/chafan/search_index"

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 1
    EMAIL_SIGNUP_CODE_EXPIRE_HOURS: int = 1

    FIRST_SUPERUSER: Optional[CaseInsensitiveEmailStr] = None
    FIRST_SUPERUSER_PASSWORD: Optional[SecretStr] = None
    VISITOR_USER_ID: Optional[int] = None

    DISABLE_RATE_LIMIT: bool = False

    API_LIMIT_SITES_GET_QUESTIONS_LIMIT: int = 20

    DEBUG_BYPASS_REDIS_VERIFICATION_CODE: Optional[str] = None
    DEBUG_ADMIN_TOOL_FULL_SITE_PASSCODE: str = "5e5da072"

    class Config:
        case_sensitive = True
        # Deliberately no `env_file`: settings come from the environment and
        # nothing else. Deployments keep their configuration in a file outside
        # the checkout, sourced before the process starts, because it holds
        # secrets that must not live in a tracked directory. A `.env` fallback
        # would be a second place for those same secrets to end up -- inside
        # the repository -- so there is none. See the README.

    ### Limit settings
    VISITORS_READ_ARTICLE_LIMIT: int = 100 #previous 5
    LIMIT_RSS_RESPONSE_ITEMS: int = 200
    LIMIT_RSS_ADMIN_TOOL_FULL_SITE_ITEMS: int = 500

    ### Cache (Redis)
    CACHE_SITEMAP_VALID_HOURS: int = 1

    ### Scheduled Tasks
    SCHEDULED_TASK_UPDATE_VIEW_COUNT_MINUTES: int = 5
    SCHEDULED_TASK_REFRESH_SEARCH_INDEX_HOURS: int = 24
    SCHEDULED_TASK_FILL_MISSING_KEYWORDS_HOURS: int = 24

    # Karma and coin amounts are NOT settings -- they are product rules, and
    # they live in `chafan_core/app/rules.py` where they can be read and
    # changed by someone who does not write Python. Redeploying the backend
    # with a different environment is harder than editing that file, not
    # easier, so the old per-deployment overrides bought nothing.



setting_keys = set(Settings.schema()["properties"].keys())


try:
    settings = Settings()
except ValidationError as e:
    # Pydantic says which settings are missing, but not the reason they are
    # usually missing. Since configuration comes from the environment only,
    # the common cause is a config file that was sourced without being
    # exported: plain `source env.ci` sets shell variables, and a child
    # process -- alembic, pytest, uvicorn -- never sees those. The symptom is
    # this error with `input_value={}`, several frames away from the mistake.
    raise RuntimeError(
        f"{e}\n\n"
        "Settings are read from environment variables only; there is no .env "
        "fallback.\n"
        "If the values are in a file, export them while sourcing it:\n"
        "    set -a; source env.ci; set +a\n"
    ) from e

if settings.SENTRY_DSN:
    sentry_sdk.init(
        settings.SENTRY_DSN,  # type: ignore
        traces_sample_rate=0.2,
        integrations=[
            RedisIntegration(),
            SqlalchemyIntegration(),
        ],
    )


############ Logging the settings ############

REDACTED = "***redacted***"

# A setting is treated as secret-bearing by its *name*, not by an explicit list
# of the secrets we happen to have today: a setting added later that carries a
# credential is redacted the moment it is named like one, without anyone having
# to remember to come back here. The cost is a few harmless redactions
# (HCAPTCHA_SITEKEY is public), which is the direction to be wrong in.
_SECRET_NAME_PARTS = (
    "SECRET",
    "PASSWORD",
    "PASSCODE",
    "TOKEN",
    "KEY",
    "CODE",
    "CREDENTIAL",
)

# Only string-valued settings are redacted, so the durations that are named like
# secrets -- ACCESS_TOKEN_EXPIRE_MINUTES, EMAIL_SIGNUP_CODE_EXPIRE_HOURS -- keep
# printing their value. An int cannot be a credential.
_SECRET_VALUE_TYPES = (str, SecretStr)

# Credentials also hide inside URLs: DATABASE_URL and REDIS_URL carry a
# password, and a Sentry DSN carries its key, all in the userinfo part before
# the `@`. Mask the whole userinfo and keep the rest, which is the half worth
# logging.
_URL_USERINFO_RE = re.compile(r"(?<=://)[^/@]+@")


def _is_secret_name(name: str) -> bool:
    return any(part in name for part in _SECRET_NAME_PARTS)


def redact_setting(name: str, value: object) -> str:
    """Render one setting for a log line, without disclosing a credential."""
    if value is None:
        # Worth logging as-is: "unset" is the answer to most configuration
        # questions, and it discloses nothing.
        return "None"
    if _is_secret_name(name) and isinstance(value, _SECRET_VALUE_TYPES):
        return REDACTED
    return _URL_USERINFO_RE.sub(f"{REDACTED}@", str(value))


def redacted_settings() -> Iterator[Tuple[str, str]]:
    """The settings as (name, loggable value) pairs, in declaration order."""
    for k, v in settings.__dict__.items():
        if not k.startswith("__"):
            yield k, redact_setting(k, v)
