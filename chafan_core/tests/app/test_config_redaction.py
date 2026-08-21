from pydantic.types import SecretStr

from chafan_core.app.config import (
    REDACTED,
    redact_setting,
    redacted_settings,
)


def test_redacts_the_named_secrets():
    for name in [
        "SECRET_KEY",
        "EMAIL_SMTP_LOGIN_PASSWORD",
        "AWS_SECRET_ACCESS_KEY",
        "UPLOADS_S3_SECRET_ACCESS_KEY",
        "UPLOADS_S3_ACCESS_KEY_ID",
        "HCAPTCHA_SECRET",
        "DEBUG_ADMIN_TOOL_FULL_SITE_PASSCODE",
        "DEBUG_BYPASS_REDIS_VERIFICATION_CODE",
    ]:
        assert redact_setting(name, "hunter2") == REDACTED, name
        assert "hunter2" not in redact_setting(name, "hunter2")


def test_redacts_secretstr():
    assert redact_setting("FIRST_SUPERUSER_PASSWORD", SecretStr("hunter2")) == REDACTED


def test_keeps_durations_that_are_merely_named_like_secrets():
    # An int is never a credential, and the value is the useful part of the line.
    assert redact_setting("ACCESS_TOKEN_EXPIRE_MINUTES", 86400) == "86400"
    assert redact_setting("EMAIL_SIGNUP_CODE_EXPIRE_HOURS", 1) == "1"


def test_keeps_unset_settings_legible():
    assert redact_setting("SECRET_KEY", None) == "None"


def test_keeps_the_plain_settings():
    assert redact_setting("ENV", "dev") == "dev"
    assert redact_setting("UPLOADS_S3_BUCKET", "chafan-uploads") == "chafan-uploads"
    assert redact_setting("PROJECT_NAME", "Chafan Dev") == "Chafan Dev"


def test_masks_credentials_embedded_in_urls():
    assert (
        redact_setting("DATABASE_URL", "postgresql://chafan:hunter2@db.local:5432/app")
        == f"postgresql://{REDACTED}@db.local:5432/app"
    )
    assert (
        redact_setting("REDIS_URL", "redis://:hunter2@cache.local:6379/0")
        == f"redis://{REDACTED}@cache.local:6379/0"
    )
    assert (
        redact_setting("SENTRY_DSN", "https://abc123@o1.ingest.sentry.io/42")
        == f"https://{REDACTED}@o1.ingest.sentry.io/42"
    )


def test_leaves_urls_without_credentials_alone():
    for url in [
        "https://uploads.cha.fan",
        "postgresql://db.local:5432/app",
        "https://account.r2.cloudflarestorage.com/bucket",
    ]:
        assert redact_setting("UPLOADS_S3_ENDPOINT_URL", url) == url


def test_the_dump_covers_every_setting_and_hides_the_live_ones():
    # Guards the wiring: the log line is built from this, so a setting that
    # stops going through `redact_setting` shows up here.
    from chafan_core.app.config import settings

    dumped = dict(redacted_settings())
    assert set(dumped) == {k for k in settings.__dict__ if not k.startswith("__")}
    for name in ["SECRET_KEY", "HCAPTCHA_SECRET", "DEBUG_ADMIN_TOOL_FULL_SITE_PASSCODE"]:
        if getattr(settings, name):
            assert dumped[name] == REDACTED
    # Whatever the deployment's connection strings look like, no userinfo
    # reaches the log.
    for name in ["DATABASE_URL", "REDIS_URL", "SENTRY_DSN"]:
        assert "@" not in dumped[name].replace(f"{REDACTED}@", "")
