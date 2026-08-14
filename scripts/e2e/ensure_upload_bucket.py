#!/usr/bin/env python3
"""Create the image-upload bucket in the configured object store, if missing.

MinIO (and Storm) start empty, and the upload endpoint does not create its own
bucket. This runs before the smoke suite so ``POST /upload/images/`` has
somewhere to write. It is a no-op when ``UPLOADS_S3_ENDPOINT_URL`` is unset, so
the suite still runs without an object store (the upload spec then skips the
store-dependent steps).

Reads the environment directly rather than ``chafan_core.app.config`` so it
works on any branch, including ones that do not yet declare the ``UPLOADS_S3_*``
settings.

Usage:
    python scripts/e2e/ensure_upload_bucket.py
"""
from __future__ import annotations

import os
import sys

import boto3
from botocore.client import Config


def main() -> int:
    endpoint = os.environ.get("UPLOADS_S3_ENDPOINT_URL")
    bucket = os.environ.get("UPLOADS_S3_BUCKET")
    if not endpoint or not bucket:
        print("no UPLOADS_S3_ENDPOINT_URL / UPLOADS_S3_BUCKET; skipping bucket creation")
        return 0

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ.get("UPLOADS_S3_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("UPLOADS_S3_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("UPLOADS_S3_REGION") or "us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    try:
        client.head_bucket(Bucket=bucket)
        print(f"upload bucket {bucket!r} already exists")
    except Exception:
        client.create_bucket(Bucket=bucket)
        print(f"created upload bucket {bucket!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
