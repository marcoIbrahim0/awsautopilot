"""
Users API endpoints for listing, inviting, and managing users within a tenant.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import (
    AuthResponse,
    create_access_token,
    get_current_user,
    get_saas_and_launch_url,
    hash_password,
    tenant_to_response,
    user_to_response,
)
from backend.database import get_db
from backend.models.enums import UserRole
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.models.user_invite import UserInvite
from backend.services.email import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

# Invite expiry duration
INVITE_EXPIRY_DAYS = 7


# ============================================
# Response Models
# ============================================

class UserListItem(BaseModel):
    """User item in list response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    role: str
    created_at: str


class InviteRequest(BaseModel):
    """Request body for inviting a user."""
    email: EmailStr = Field(..., description="Email address to invite")


class InviteResponse(BaseModel):
    """Response for successful invite."""
    message: str
    email: str


class AcceptInviteInfoResponse(BaseModel):
    """Response for GET accept-invite (invite details)."""
    email: str
    tenant_name: str
    inviter_name: str


class AcceptInviteRequest(BaseModel):
    """Request body for accepting an invite."""
    token: str = Field(..., description="Invite token from the link")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")
    name: str = Field(..., min_length=1, max_length=255, description="User's full name")


class UpdateMeRequest(BaseModel):
    """Request body for updating current user."""
    onboarding_completed: bool | None = Field(None, description="Mark onboarding as completed")
    name: str | None = Field(None, min_length=1, max_length=255, description="Update user name")


class UpdateMeResponse(BaseModel):
    """Response for updating current user."""
    user: dict


class DigestSettingsResponse(BaseModel):
    """Response for GET digest settings (Step 11.3)."""
    digest_enabled: bool
    digest_recipients: str | None = None


class DigestSettingsUpdateRequest(BaseModel):
    """Request body for PATCH digest settings (Step 11.3)."""
    digest_enabled: bool | None = Field(None, description="Enable or disable weekly digest email")
    digest_recipients: str | None = Field(
        None,
        max_length=2000,
        description="Comma-separated email addresses; if null/empty, digest goes to tenant admins",
    )


class SlackSettingsResponse(BaseModel):
    """Response for GET slack settings (Step 11.4). Webhook URL is never returned."""
    slack_webhook_configured: bool = Field(
        ...,
        description="True if a Slack webhook URL is configured (URL itself is not exposed).",
    )
    slack_digest_enabled: bool = Field(
        ...,
        description="True if weekly digest is posted to Slack when webhook is configured.",
    )


class SlackSettingsUpdateRequest(BaseModel):
    """Request body for PATCH slack settings (Step 11.4)."""
    slack_webhook_url: str | None = Field(
        None,
        max_length=2000,
        description="Slack incoming webhook URL; set to empty string to clear.",
    )
    slack_digest_enabled: bool | None = Field(
        None,
        description="Enable or disable posting weekly digest to Slack.",
    )


# ============================================
# Endpoints
# ============================================

@router.get("", response_model=list[UserListItem])
async def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[UserListItem]:
    """
    List all users in the current user's tenant.
    
    Requires authentication.
    """
    result = await db.execute(
        select(User)
        .where(User.tenant_id == current_user.tenant_id)
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()

    def _role_str(r) -> str:
        return getattr(r, "value", r) if r is not None else "member"

    return [
        UserListItem(
            id=str(u.id),
            email=u.email,
            name=u.name,
            role=_role_str(u.role),
            created_at=u.created_at.isoformat() if u.created_at else "",
        )
        for u in users
    ]


@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    request: InviteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> InviteResponse:
    """
    Invite a user to join the tenant by email.
    
    Requires authentication and admin role.
    Creates an invite record and sends an email with an invite link.
    """
    # Check admin role (role may be enum or str from DB)
    if getattr(current_user.role, "value", current_user.role) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can invite users",
        )
    
    # Check if email already exists as a user
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    
    # Check if invite already exists for this email in this tenant
    result = await db.execute(
        select(UserInvite).where(
            UserInvite.tenant_id == current_user.tenant_id,
            UserInvite.email == request.email,
        )
    )
    existing_invite = result.scalar_one_or_none()
    
    if existing_invite:
        # Update existing invite with new token and expiry
        existing_invite.token = uuid.uuid4()
        existing_invite.expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRY_DAYS)
        existing_invite.created_by_user_id = current_user.id
        await db.commit()
        await db.refresh(existing_invite)
        invite = existing_invite
    else:
        # Create new invite
        invite = UserInvite(
            tenant_id=current_user.tenant_id,
            email=request.email,
            token=uuid.uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRY_DAYS),
            created_by_user_id=current_user.id,
        )
        db.add(invite)
        await db.commit()
        await db.refresh(invite)
    
    # Send invite email
    email_service.send_invite_email(
        to_email=request.email,
        invite_token=str(invite.token),
        tenant_name=current_user.tenant.name,
        inviter_name=current_user.name,
    )
    
    logger.info(f"User {current_user.id} invited {request.email} to tenant {current_user.tenant_id}")
    
    return InviteResponse(
        message=f"Invitation sent to {request.email}",
        email=request.email,
    )


@router.get("/accept-invite", response_model=AcceptInviteInfoResponse)
async def get_invite_info(
    token: Annotated[str, Query(..., description="Invite token from the link")],
    db: AsyncSession = Depends(get_db),
) -> AcceptInviteInfoResponse:
    """
    Get invite information for display before accepting.
    
    Does not require authentication.
    Validates the token and returns invite details.
    """
    # Validate token format
    try:
        token_uuid = uuid.UUID(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite token format",
        )
    
    # Find invite with related data
    result = await db.execute(
        select(UserInvite)
        .options(
            selectinload(UserInvite.tenant),
            selectinload(UserInvite.created_by_user),
        )
        .where(UserInvite.token == token_uuid)
    )
    invite = result.scalar_one_or_none()
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found or expired",
        )
    
    # Check expiry
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invite has expired",
        )
    
    return AcceptInviteInfoResponse(
        email=invite.email,
        tenant_name=invite.tenant.name,
        inviter_name=invite.created_by_user.name if invite.created_by_user else "Team Admin",
    )


@router.post("/accept-invite", response_model=AuthResponse)
async def accept_invite(
    request: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Accept an invitation and create/update user account.
    
    Does not require authentication.
    Validates the token, creates/updates the user, and returns a JWT.
    """
    # Validate token format
    try:
        token_uuid = uuid.UUID(request.token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite token format",
        )
    
    # Find invite with tenant
    result = await db.execute(
        select(UserInvite)
        .options(selectinload(UserInvite.tenant))
        .where(UserInvite.token == token_uuid)
    )
    invite = result.scalar_one_or_none()
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found or expired",
        )
    
    # Check expiry
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invite has expired",
        )
    
    # Check if user already exists with this email
    result = await db.execute(select(User).where(User.email == invite.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        # User exists - update their password and tenant if needed
        # This handles edge cases where user was created but never set password
        existing_user.password_hash = hash_password(request.password)
        existing_user.name = request.name
        user = existing_user
    else:
        # Create new user
        user = User(
            tenant_id=invite.tenant_id,
            email=invite.email,
            name=request.name,
            password_hash=hash_password(request.password),
            role=UserRole.member,
        )
        db.add(user)
    
    # Delete the invite (consumed)
    await db.delete(invite)
    await db.commit()
    await db.refresh(user)
    
    # Load tenant for response
    result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = result.scalar_one()
    
    # Create JWT
    access_token = create_access_token(user.id, user.tenant_id)
    
    logger.info(f"User {user.id} accepted invite for tenant {user.tenant_id}")
    
    (
        saas_id,
        read_launch_url,
        read_template_url,
        write_launch_url,
        write_template_url,
        region,
        read_default_stack,
        write_default_stack,
    ) = get_saas_and_launch_url(tenant.external_id)
    return AuthResponse(
        access_token=access_token,
        user=user_to_response(user),
        tenant=tenant_to_response(tenant),
        saas_account_id=saas_id,
        read_role_launch_stack_url=read_launch_url,
        read_role_template_url=read_template_url,
        read_role_region=region,
        read_role_default_stack_name=read_default_stack,
        write_role_launch_stack_url=write_launch_url,
        write_role_template_url=write_template_url,
        write_role_default_stack_name=write_default_stack,
    )


@router.patch("/me", response_model=UpdateMeResponse)
async def update_me(
    request: UpdateMeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> UpdateMeResponse:
    """
    Update current user's profile.
    
    Requires authentication.
    Used to mark onboarding as complete or update name.
    """
    if request.onboarding_completed is True:
        current_user.onboarding_completed_at = datetime.now(timezone.utc)
    
    if request.name is not None:
        current_user.name = request.name
    
    await db.commit()
    await db.refresh(current_user)
    
    logger.info(f"User {current_user.id} updated profile")
    
    role_str = getattr(current_user.role, "value", current_user.role) or "member"
    return UpdateMeResponse(
        user={
            "id": str(current_user.id),
            "email": current_user.email,
            "name": current_user.name,
            "role": role_str if isinstance(role_str, str) else str(role_str),
            "onboarding_completed_at": current_user.onboarding_completed_at.isoformat() if current_user.onboarding_completed_at else None,
        }
    )


@router.get("/me/digest-settings", response_model=DigestSettingsResponse)
async def get_digest_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> DigestSettingsResponse:
    """
    Get current tenant's weekly digest settings (Step 11.3).

    Requires authentication. Returns digest_enabled and digest_recipients
    (comma-separated; null means digest goes to tenant admins).
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return DigestSettingsResponse(
        digest_enabled=getattr(tenant, "digest_enabled", True),
        digest_recipients=getattr(tenant, "digest_recipients", None),
    )


@router.patch("/me/digest-settings", response_model=DigestSettingsResponse)
async def update_digest_settings(
    request: DigestSettingsUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> DigestSettingsResponse:
    """
    Update current tenant's weekly digest settings (Step 11.3).

    Requires authentication and admin role. digest_recipients: comma-separated
    emails; set to empty string to clear (digest will then go to tenant admins).
    """
    if getattr(current_user.role, "value", current_user.role) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update digest settings",
        )
    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    if request.digest_enabled is not None:
        tenant.digest_enabled = request.digest_enabled
    if request.digest_recipients is not None:
        tenant.digest_recipients = request.digest_recipients.strip() or None
    await db.commit()
    await db.refresh(tenant)
    return DigestSettingsResponse(
        digest_enabled=tenant.digest_enabled,
        digest_recipients=tenant.digest_recipients,
    )


@router.get("/me/slack-settings", response_model=SlackSettingsResponse)
async def get_slack_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> SlackSettingsResponse:
    """
    Get current tenant's Slack digest settings (Step 11.4).

    Requires authentication. Webhook URL is never returned; only whether it is configured.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    webhook = getattr(tenant, "slack_webhook_url", None) or ""
    return SlackSettingsResponse(
        slack_webhook_configured=bool(webhook.strip()),
        slack_digest_enabled=getattr(tenant, "slack_digest_enabled", False),
    )


@router.patch("/me/slack-settings", response_model=SlackSettingsResponse)
async def update_slack_settings(
    request: SlackSettingsUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> SlackSettingsResponse:
    """
    Update current tenant's Slack digest settings (Step 11.4).

    Requires authentication and admin role. slack_webhook_url: set to empty string
    to clear (Slack digest will stop until a new URL is set).
    """
    if getattr(current_user.role, "value", current_user.role) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update Slack settings",
        )
    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    if request.slack_webhook_url is not None:
        tenant.slack_webhook_url = request.slack_webhook_url.strip() or None
    if request.slack_digest_enabled is not None:
        tenant.slack_digest_enabled = request.slack_digest_enabled
    await db.commit()
    await db.refresh(tenant)
    webhook = getattr(tenant, "slack_webhook_url", None) or ""
    return SlackSettingsResponse(
        slack_webhook_configured=bool(webhook.strip()),
        slack_digest_enabled=tenant.slack_digest_enabled,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: Annotated[str, Path(..., description="User ID to delete")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a user from the tenant.
    
    Requires authentication and admin role.
    Users cannot delete themselves.
    """
    # Check admin role (role may be enum or str from DB)
    if getattr(current_user.role, "value", current_user.role) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete users",
        )
    
    # Validate user_id format
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format",
        )
    
    # Cannot delete yourself
    if user_uuid == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    
    # Find user in same tenant
    result = await db.execute(
        select(User).where(
            User.id == user_uuid,
            User.tenant_id == current_user.tenant_id,
        )
    )
    user_to_delete = result.scalar_one_or_none()
    
    if not user_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    await db.delete(user_to_delete)
    await db.commit()
    
    logger.info(f"Admin {current_user.id} deleted user {user_id} from tenant {current_user.tenant_id}")
