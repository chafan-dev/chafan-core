#!/usr/bin/env python3
"""Check that stored image URLs are actually fetchable without credentials.

The write path and the read path use two different hosts, and nothing in the
server ever exercises the read one: ``UPLOADS_PUBLIC_URL_BASE`` is only string
-concatenated into the response. So a base pointed at the wrong host fails
silently -- uploads return 200, the bytes land, and only a browser ever finds
out. This walks the chain the browser walks.

For each object in the bucket it builds ``<base>/<key>`` and fetches it with no
signature, then compares what came back against the signed ``head_object``:
status, content type, and length. It also refuses the specific mistake that
prompted it, a public base equal to the S3 endpoint -- Garage serves no
anonymous request there, so every such URL 403s.

Reads the environment directly, like ``scripts/e2e/ensure_upload_bucket.py``.

Usage:
    python scripts/check_upload_public_read.py            # every object
    python scripts/check_upload_public_read.py --limit=5
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request

import boto3
from botocore.client import Config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="check at most N objects")
    args = parser.parse_args()

    endpoint = os.environ.get("UPLOADS_S3_ENDPOINT_URL")
    bucket = os.environ.get("UPLOADS_S3_BUCKET")
    base = (os.environ.get("UPLOADS_PUBLIC_URL_BASE") or "").rstrip("/")
    if not endpoint or not bucket or not base:
        print("UPLOADS_S3_ENDPOINT_URL / UPLOADS_S3_BUCKET / UPLOADS_PUBLIC_URL_BASE"
              " must all be set")
        return 2

    if base.rstrip("/") == endpoint.rstrip("/"):
        print(f"UPLOADS_PUBLIC_URL_BASE is the S3 endpoint ({base}).")
        print("Garage serves no anonymous request there. Point it at the read"
              " proxy instead (see workers/uploads-proxy/README.md).")
        return 1

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ.get("UPLOADS_S3_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("UPLOADS_S3_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("UPLOADS_S3_REGION") or "us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    keys = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        keys.extend(o["Key"] for o in page.get("Contents", []))
    if args.limit:
        keys = keys[: args.limit]
    if not keys:
        print(f"bucket {bucket!r} is empty; nothing to check")
        return 0

    failures = 0
    for key in keys:
        head = client.head_object(Bucket=bucket, Key=key)
        url = f"{base}/{key}"
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                body = resp.read()
                status, content_type = resp.status, resp.headers.get("Content-Type")
        except urllib.error.HTTPError as e:
            print(f"FAIL {key}: HTTP {e.code} at {url}")
            failures += 1
            continue
        except Exception as e:
            print(f"FAIL {key}: {type(e).__name__}: {e} at {url}")
            failures += 1
            continue

        mismatches = []
        if len(body) != head["ContentLength"]:
            mismatches.append(f"length {len(body)} != {head['ContentLength']}")
        if content_type != head["ContentType"]:
            mismatches.append(f"content-type {content_type!r} != {head['ContentType']!r}")
        if mismatches:
            print(f"FAIL {key}: {'; '.join(mismatches)}")
            failures += 1
        else:
            print(f"ok   {key}: {status} {content_type} {len(body)} bytes")

    print(f"\n{len(keys) - failures}/{len(keys)} objects publicly readable at {base}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
