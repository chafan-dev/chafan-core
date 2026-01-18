from typing import Literal, Optional

import sentry_sdk
from pydantic import AnyHttpUrl
from pydantic.types import SecretStr
from pydantic_settings import BaseSettings
from sentry_sdk.integrations.dramatiq import DramatiqIntegration
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
    AWS_CLOUDFRONT_HOST: Optional[AnyHttpUrl] = None
    CLOUDFRONT_HOST: Optional[AnyHttpUrl] = None
    S3_UPLOADS_BUCKET_NAME: Optional[str] = None

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

    OFFICIAL_BOT_SECRET: Optional[str] = None

    FORCE_RATE_LIMIT: bool = False

    API_LIMIT_SITES_GET_QUESTIONS_LIMIT: int = 20

    DEBUG_BYPASS_REDIS_VERIFICATION_CODE: Optional[str] = None
    DEBUG_ADMIN_TOOL_FULL_SITE_PASSCODE: str = "5e5da072"

    class Config:
        case_sensitive = True

    ### Limit settings
    VISITORS_READ_ARTICLE_LIMIT: int = 100  # previous 5
    LIMIT_RSS_RESPONSE_ITEMS: int = 200
    LIMIT_RSS_ADMIN_TOOL_FULL_SITE_ITEMS: int = 500

    ### Cache (Redis)
    CACHE_SITEMAP_VALID_HOURS: int = 1

    ### Scheduled Tasks
    SCHEDULED_TASK_UPDATE_VIEW_COUNT_MINUTES: int = 5
    SCHEDULED_TASK_REFRESH_SEARCH_INDEX_HOURS: int = 24

    MIN_KARMA_CREATE_PUBLIC_SITE: int = 100
    MIN_KARMA_CREATE_PRIVATE_SITE: int = 10

    INVITE_NEW_USER_COIN_PAYMENT_AMOUNT: int = 5
    CREATE_ARTICLE_COIN_DEDUCTION: int = 2
    UPVOTE_ARTICLE_COIN_DEDUCTION: int = 2
    CREATE_SITE_COIN_DEDUCTION: int = 10
    CREATE_SITE_FORCE_NEED_APPROVAL: bool = True


setting_keys = set(Settings.schema()["properties"].keys())

settings = Settings()

if settings.SENTRY_DSN:
    sentry_sdk.init(
        settings.SENTRY_DSN,  # type: ignore
        traces_sample_rate=0.2,
        integrations=[
            RedisIntegration(),
            SqlalchemyIntegration(),
            DramatiqIntegration(),
        ],
    )
