from __future__ import annotations

import uuid
from typing import Annotated

import boto3
from botocore.config import Config
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.config import settings
from backend.database import get_db
from backend.models.support_file import SupportFile
from backend.models.user import User

router = APIRouter(prefix="/support-files", tags=["support-files"])


class TenantSupportFileItemResponse(BaseModel):
    id: str
    filename: str
    content_type: str | None
    size_bytes: int | None
    message: str | None
    uploaded_at: str | None
    created_at: str


class SupportFileDownloadResponse(BaseModel):
    download_url: str


def _support_s3_client():
    region = (settings.S3_SUPPORT_BUCKET_REGION or "").strip() or settings.AWS_REGION
    return boto3.client("s3", region_name=region, config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))


@router.get("", response_model=list[TenantSupportFileItemResponse])
async def list_tenant_support_files(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TenantSupportFileItemResponse]:
    result = await db.execute(
        select(SupportFile)
        .where(
            SupportFile.tenant_id == current_user.tenant_id,
            SupportFile.visible_to_tenant.is_(True),
            SupportFile.status == "available",
        )
        .order_by(SupportFile.created_at.desc())
    )
    files = list(result.scalars().all())
    return [
        TenantSupportFileItemResponse(
            id=str(item.id),
            filename=item.filename,
            content_type=item.content_type,
            size_bytes=item.size_bytes,
            message=item.message,
            uploaded_at=item.uploaded_at.isoformat() if item.uploaded_at else None,
            created_at=item.created_at.isoformat() if item.created_at else "",
        )
        for item in files
    ]


@router.get("/{file_id}/download", response_model=SupportFileDownloadResponse)
async def get_tenant_support_file_download_url(
    file_id: Annotated[str, Path()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SupportFileDownloadResponse:
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="file_id must be a valid UUID") from exc
    result = await db.execute(
        select(SupportFile).where(
            SupportFile.id == file_uuid,
            SupportFile.tenant_id == current_user.tenant_id,
            SupportFile.visible_to_tenant.is_(True),
            SupportFile.status == "available",
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Support file not found")
    client = _support_s3_client()
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": item.s3_bucket, "Key": item.s3_key},
        ExpiresIn=3600,
    )
    return SupportFileDownloadResponse(download_url=url)
