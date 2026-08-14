"""Object storage for image uploads, backed by an S3-compatible provider.

Storm Buckets is S3-compatible (Garage underneath), so boto3 works, but the
client must be configured for it: ``s3v4`` signing and path-style addressing.
Garage-backed endpoints generally need path-style, since virtual-hosted style
requires wildcard DNS that Storm does not provide.

Deliberately separate from ``aws.py``: that module still serves SES and SNS,
while this one owns the upload bucket end to end -- the client, the object key
format, and the public URL. It is cached (one client, not one per request).

The stored URL is always our own domain (``UPLOADS_PUBLIC_URL_BASE``), never the
provider's hostname, so switching vendors is a CNAME change plus a bucket copy
rather than a rewrite of every URL embedded in a body.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import boto3
from botocore.client import Config

from chafan_core.app.config import settings

# Content-type -> file extension. Owned here so the storage key and the URL are
# derived in one place rather than stored twice.
_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


def is_configured() -> bool:
    return settings.UPLOADS_S3_ENDPOINT_URL is not None


@lru_cache(maxsize=1)
def _client() -> Any:
    endpoint = settings.UPLOADS_S3_ENDPOINT_URL
    if endpoint is None:
        raise RuntimeError(
            "image uploads are not configured: UPLOADS_S3_ENDPOINT_URL is unset"
        )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.UPLOADS_S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.UPLOADS_S3_SECRET_ACCESS_KEY,
        region_name=settings.UPLOADS_S3_REGION,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def _key(sha: str, content_type: str) -> str:
    ext = _CONTENT_TYPE_EXTENSIONS.get(content_type)
    if ext is None:
        raise ValueError(f"unsupported content type: {content_type}")
    return f"{sha}.{ext}"


def put_image(*, sha: str, content_type: str, data: bytes) -> None:
    """Store the sanitized bytes for ``sha``. Idempotent: same key, same bytes."""
    _client().put_object(
        Bucket=settings.UPLOADS_S3_BUCKET,
        Key=_key(sha, content_type),
        Body=data,
        ContentType=content_type,
        CacheControl="public, max-age=31536000, immutable",
    )


def public_url(sha: str, content_type: str) -> str:
    base = settings.UPLOADS_PUBLIC_URL_BASE
    if base is None:
        raise RuntimeError(
            "image uploads are not configured: UPLOADS_PUBLIC_URL_BASE is unset"
        )
    return f"{base}/{_key(sha, content_type)}"
