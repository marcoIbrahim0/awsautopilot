from __future__ import annotations

import uuid
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile

from backend.config import settings
from backend.models.help_case_attachment import HelpCaseAttachment


def support_s3_client():
    region = (settings.S3_SUPPORT_BUCKET_REGION or "").strip() or settings.AWS_REGION
    return boto3.client("s3", region_name=region, config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))


def support_bucket_name() -> str:
    bucket = (settings.S3_SUPPORT_BUCKET or "").strip()
    if not bucket:
        raise HTTPException(status_code=503, detail="S3_SUPPORT_BUCKET is not configured")
    return bucket


def upload_case_attachment(
    *,
    case_id: uuid.UUID,
    message_id: uuid.UUID,
    tenant_id: uuid.UUID,
    file: UploadFile,
    internal_only: bool,
    uploaded_by_user_id: uuid.UUID | None,
) -> HelpCaseAttachment:
    bucket = support_bucket_name()
    key = f"help-cases/{tenant_id}/{case_id}/{message_id}/{uuid.uuid4()}/{file.filename}"
    client = support_s3_client()
    size_bytes = None
    try:
        file.file.seek(0, 2)
        size_bytes = file.file.tell()
        file.file.seek(0)
    except Exception:
        size_bytes = None
    try:
        extra = {"ContentType": file.content_type} if file.content_type else {}
        client.upload_fileobj(file.file, bucket, key, ExtraArgs=extra)
    except ClientError as exc:
        raise HTTPException(status_code=502, detail="S3 upload failed") from exc
    return HelpCaseAttachment(
        case_id=case_id,
        message_id=message_id,
        tenant_id=tenant_id,
        uploaded_by_user_id=uploaded_by_user_id,
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=size_bytes,
        s3_bucket=bucket,
        s3_key=key,
        internal_only=internal_only,
        uploaded_at=datetime.now(timezone.utc),
    )


def build_case_attachment_download_url(attachment: HelpCaseAttachment) -> str:
    client = support_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": attachment.s3_bucket, "Key": attachment.s3_key},
        ExpiresIn=3600,
    )
