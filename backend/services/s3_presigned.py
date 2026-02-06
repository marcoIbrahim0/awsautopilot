"""
Presigned S3 URL generation for downloads (Step 10.5, 13.3).

Shared helper for evidence exports and baseline reports so API and worker
can generate time-limited download URLs. Uses AWS Signature Version 4;
client region must match bucket region.
"""
from __future__ import annotations

import logging
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from backend.config import settings
from backend.services.evidence_export_s3 import PRESIGNED_URL_EXPIRES_IN

logger = logging.getLogger(__name__)


def generate_presigned_url(
    bucket: str,
    key: str,
    region: Optional[str] = None,
    expires_in: int = PRESIGNED_URL_EXPIRES_IN,
) -> str:
    """
    Generate a presigned GET URL for an S3 object.

    Uses s3v4 signature; path-style addressing for compatibility.
    Caller must have s3:GetObject on the bucket/key.

    Args:
        bucket: S3 bucket name.
        key: S3 object key.
        region: AWS region for the bucket; defaults to S3_EXPORT_BUCKET_REGION or AWS_REGION.
        expires_in: URL expiry in seconds (default 3600).

    Returns:
        Presigned URL string.

    Raises:
        ClientError: On boto3 failure (e.g. invalid bucket/region).
    """
    reg = (region or "").strip() or (settings.S3_EXPORT_BUCKET_REGION or "").strip() or settings.AWS_REGION
    s3_config = Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
    )
    s3 = boto3.client("s3", region_name=reg, config=s3_config)
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
