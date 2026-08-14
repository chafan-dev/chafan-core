"""Integration: boto3 upload wiring against a real S3-compatible store.

MinIO is not Garage, and neither container exercises Storm's public serving
layer, but it does prove the client is provider-neutral: that ``endpoint_url``,
path-style addressing and s3v4 signing all work against a non-AWS S3. Run in CI
with a MinIO service container and ``UPLOADS_S3_*`` set; skipped otherwise.
"""

import io

import boto3
import pytest
from botocore.client import Config
from PIL import Image

from chafan_core.app import object_storage
from chafan_core.app.config import settings

pytestmark = pytest.mark.skipif(
    settings.UPLOADS_S3_ENDPOINT_URL is None,
    reason="UPLOADS_S3_ENDPOINT_URL is not set (no MinIO running)",
)


def _png(rgb=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), rgb).save(buf, format="PNG")
    return buf.getvalue()


def _raw_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.UPLOADS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.UPLOADS_S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.UPLOADS_S3_SECRET_ACCESS_KEY,
        region_name=settings.UPLOADS_S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def test_put_image_round_trip():
    assert settings.UPLOADS_S3_BUCKET is not None
    sha = "a" * 64
    raw = _png()
    client = _raw_client()
    bucket = settings.UPLOADS_S3_BUCKET
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)

    object_storage.put_image(sha=sha, content_type="image/png", data=raw)

    got = client.get_object(Bucket=bucket, Key=f"{sha}.png")
    assert got["Body"].read() == raw
    assert got["ContentType"] == "image/png"
    assert got["CacheControl"] == "public, max-age=31536000, immutable"

    assert (
        object_storage.public_url(sha, "image/png")
        == f"{settings.UPLOADS_PUBLIC_URL_BASE}/{sha}.png"
    )
