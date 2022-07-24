from typing import Any

import boto3

from chafan_core.app.config import settings


def get_boto3_client() -> boto3.Session:  # type: ignore
    assert settings.AWS_ACCESS_KEY_ID is not None
    assert settings.AWS_SECRET_ACCESS_KEY is not None
    assert settings.AWS_REGION is not None
    boto_kwargs = {
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        "region_name": settings.AWS_REGION,
    }
    return boto3.Session(**boto_kwargs)  # type: ignore


def get_s3_client() -> Any:
    return get_boto3_client().client("s3")


def get_ses_client() -> Any:
    return get_boto3_client().client("ses")


def get_sns_client() -> Any:
    return get_boto3_client().client("sns")
