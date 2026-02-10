"""
Authentication module for JWT-based auth.

Provides:
- Password hashing (bcrypt directly; no passlib to avoid version conflicts)
- JWT token creation and verification
- FastAPI dependencies: get_optional_user, get_current_user
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from urllib.parse import urlencode

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import get_db
from backend.models.user import User
from backend.services.cloudformation_templates import get_latest_template_version

logger = logging.getLogger(__name__)

# Bearer token security scheme (auto_error=False for optional auth)
bearer_scheme = HTTPBearer(auto_error=False)

# JWT settings
JWT_ALGORITHM = "HS256"


# ============================================
# Pydantic models for auth responses
# ============================================

class TokenData(BaseModel):
    """Data encoded in JWT."""
    sub: str  # user_id as string
    tenant_id: str
    exp: datetime


class UserResponse(BaseModel):
    """User data in auth responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    role: str
    onboarding_completed_at: str | None
    is_saas_admin: bool = False


class TenantResponse(BaseModel):
    """Tenant data in auth responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    external_id: str


# Default CloudFormation stack name for Read Role; user can override if name is taken
DEFAULT_READ_ROLE_STACK_NAME = "SecurityAutopilotReadRole"
DEFAULT_WRITE_ROLE_STACK_NAME = "SecurityAutopilotWriteRole"
DEFAULT_CONTROL_PLANE_FORWARDER_STACK_NAME = "SecurityAutopilotControlPlaneForwarder"


class AuthResponse(BaseModel):
    """Response for login/signup endpoints."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    tenant: TenantResponse
    saas_account_id: str | None = None
    read_role_launch_stack_url: str | None = None
    # For building Launch Stack URL with custom stack name (e.g. SecurityAutopilotReadRole-2)
    read_role_template_url: str | None = None
    read_role_region: str | None = None
    read_role_default_stack_name: str = DEFAULT_READ_ROLE_STACK_NAME
    write_role_launch_stack_url: str | None = None
    write_role_template_url: str | None = None
    write_role_default_stack_name: str = DEFAULT_WRITE_ROLE_STACK_NAME
    # Control-plane event forwarder (Phase 1)
    control_plane_token: str | None = None
    control_plane_forwarder_template_url: str | None = None
    control_plane_ingest_url: str | None = None
    control_plane_forwarder_default_stack_name: str = DEFAULT_CONTROL_PLANE_FORWARDER_STACK_NAME


class MeResponse(BaseModel):
    """Response for GET /api/auth/me."""
    user: UserResponse
    tenant: TenantResponse
    # For "Deploy Read Role" Launch Stack link (S3/CloudFront versioned template)
    saas_account_id: str | None = None
    read_role_launch_stack_url: str | None = None
    read_role_template_url: str | None = None
    read_role_region: str | None = None
    read_role_default_stack_name: str = DEFAULT_READ_ROLE_STACK_NAME
    write_role_launch_stack_url: str | None = None
    write_role_template_url: str | None = None
    write_role_default_stack_name: str = DEFAULT_WRITE_ROLE_STACK_NAME
    # Control-plane event forwarder (Phase 1)
    control_plane_token: str | None = None
    control_plane_forwarder_template_url: str | None = None
    control_plane_ingest_url: str | None = None
    control_plane_forwarder_default_stack_name: str = DEFAULT_CONTROL_PLANE_FORWARDER_STACK_NAME


# ============================================
# Password utilities (bcrypt directly; 72-byte limit enforced)
# ============================================

BCRYPT_MAX_PASSWORD_BYTES = 72


def _password_bytes(password: str) -> bytes:
    """Encode password to bytes and truncate to 72 bytes for bcrypt."""
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        encoded = encoded[:BCRYPT_MAX_PASSWORD_BYTES]
    return encoded


def hash_password(password: str) -> str:
    """Hash a password using bcrypt (password truncated to 72 bytes if longer)."""
    pw_bytes = _password_bytes(password)
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    pw_bytes = _password_bytes(plain_password)
    try:
        return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ============================================
# JWT utilities
# ============================================

def create_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    """
    Create a JWT access token for a user.
    
    Token contains: user_id (sub), tenant_id, expiration.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenData | None:
    """
    Decode and validate a JWT access token.
    
    Returns TokenData if valid, None if invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return TokenData(
            sub=payload["sub"],
            tenant_id=payload["tenant_id"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ============================================
# FastAPI dependencies
# ============================================

async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Dependency that returns the current user if authenticated, else None.
    
    Does NOT raise 401 if no token is present. Use for optional auth on
    endpoints that support both authenticated and unauthenticated access.
    """
    if credentials is None:
        return None
    
    token_data = decode_access_token(credentials.credentials)
    if token_data is None:
        return None
    
    try:
        user_id = uuid.UUID(token_data.sub)
    except ValueError:
        return None
    
    # Fetch user with tenant eagerly loaded
    result = await db.execute(
        select(User)
        .options(selectinload(User.tenant))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    return user


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency that returns the current user or raises 401.
    
    Use for endpoints that require authentication.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = decode_access_token(credentials.credentials)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = uuid.UUID(token_data.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fetch user with tenant eagerly loaded
    result = await db.execute(
        select(User)
        .options(selectinload(User.tenant))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


# ============================================
# Helper functions
# ============================================

def user_to_response(user: User) -> UserResponse:
    """Convert User model to UserResponse."""
    # Role may be UserRole enum or str after DB load
    role = getattr(user.role, "value", user.role) if user.role is not None else "member"
    if not isinstance(role, str):
        role = str(role)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=role,
        onboarding_completed_at=user.onboarding_completed_at.isoformat() if user.onboarding_completed_at else None,
        is_saas_admin=is_saas_admin_email(user.email),
    )


def tenant_to_response(tenant) -> TenantResponse:
    """Convert Tenant model to TenantResponse."""
    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        external_id=tenant.external_id,
    )


def _sanitize_stack_name(name: str, default_stack_name: str) -> str:
    """CloudFormation stack names: alphanumeric and hyphens only; max 128 chars."""
    sanitized = "".join(c if c.isalnum() or c == "-" else "-" for c in (name or "").strip())
    return sanitized[:128] if sanitized else default_stack_name


def build_launch_stack_url(
    template_url: str,
    region: str,
    external_id: str,
    saas_account_id: str,
    stack_name: str | None = None,
    default_stack_name: str = DEFAULT_READ_ROLE_STACK_NAME,
) -> str:
    """
    Build CloudFormation console 'Launch Stack' URL with prefilled template and parameters.

    Console deep link: /stacks/create/template with templateURL, stackName, and param_*
    in the hash fragment so the user sees everything filled when they click Next.
    Parameter keys must match the template (prefixed with param_): param_ExternalId, param_SaaSAccountId.
    stack_name: optional; if the default name is already in use, use e.g. SecurityAutopilotReadRole-2.
    """
    base = f"https://{region}.console.aws.amazon.com/cloudformation/home?region={region}"
    name = _sanitize_stack_name(stack_name or "", default_stack_name)
    params = {
        "templateURL": template_url.strip(),
        "stackName": name,
        "param_SaaSAccountId": saas_account_id.strip(),
        "param_ExternalId": external_id,
    }
    return f"{base}#/stacks/create/template?{urlencode(params)}"


def build_read_role_launch_stack_url(
    template_url: str,
    region: str,
    external_id: str,
    saas_account_id: str,
    stack_name: str | None = None,
) -> str:
    return build_launch_stack_url(
        template_url=template_url,
        region=region,
        external_id=external_id,
        saas_account_id=saas_account_id,
        stack_name=stack_name,
        default_stack_name=DEFAULT_READ_ROLE_STACK_NAME,
    )


def build_write_role_launch_stack_url(
    template_url: str,
    region: str,
    external_id: str,
    saas_account_id: str,
    stack_name: str | None = None,
) -> str:
    return build_launch_stack_url(
        template_url=template_url,
        region=region,
        external_id=external_id,
        saas_account_id=saas_account_id,
        stack_name=stack_name,
        default_stack_name=DEFAULT_WRITE_ROLE_STACK_NAME,
    )


def get_saas_and_launch_url(
    external_id: str,
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str,
    str,
    str | None,
    str | None,
    str,
]:
    """
    Return:
    (
      saas_account_id,
      read_role_launch_stack_url,
      read_role_template_url,
      write_role_launch_stack_url,
      write_role_template_url,
      region,
      read_role_default_stack_name,
      write_role_default_stack_name,
      control_plane_forwarder_template_url,
      control_plane_ingest_url,
      control_plane_forwarder_default_stack_name,
    )

    Launch URLs and template URLs are None when corresponding template URL is not configured.
    Automatically detects the latest template version from S3 if the base URL is configured.
    """
    saas_account_id = (settings.SAAS_AWS_ACCOUNT_ID or "").strip() or None
    read_template_url = (settings.CLOUDFORMATION_READ_ROLE_TEMPLATE_URL or "").strip()
    write_template_url = (settings.CLOUDFORMATION_WRITE_ROLE_TEMPLATE_URL or "").strip()
    control_plane_template_url = (settings.CLOUDFORMATION_CONTROL_PLANE_FORWARDER_TEMPLATE_URL or "").strip()
    region = (settings.CLOUDFORMATION_DEFAULT_REGION or "").strip() or "eu-north-1"

    control_plane_ingest_url: str | None = None
    api_public_url = (settings.API_PUBLIC_URL or "").strip()
    if api_public_url:
        control_plane_ingest_url = api_public_url.rstrip("/") + "/api/control-plane/events"

    if control_plane_template_url:
        latest_template_url = get_latest_template_version(control_plane_template_url)
        if latest_template_url:
            control_plane_template_url = latest_template_url
            logger.debug(
                "Using latest control-plane forwarder template version: %s",
                control_plane_template_url,
            )
        else:
            logger.warning(
                "Failed to detect latest control-plane forwarder template version, using configured URL: %s",
                control_plane_template_url,
            )
    if not control_plane_template_url:
        control_plane_template_url = None

    read_launch_url: str | None = None
    write_launch_url: str | None = None

    if saas_account_id and external_id and read_template_url:
        latest_template_url = get_latest_template_version(read_template_url)
        if latest_template_url:
            read_template_url = latest_template_url
            logger.debug(f"Using latest read-role template version: {read_template_url}")
        else:
            logger.warning(
                f"Failed to detect latest read-role template version, using configured URL: {read_template_url}"
            )

        read_launch_url = build_read_role_launch_stack_url(
            template_url=read_template_url,
            region=region,
            external_id=external_id,
            saas_account_id=saas_account_id,
            stack_name=DEFAULT_READ_ROLE_STACK_NAME,
        )

    if saas_account_id and external_id and write_template_url:
        latest_template_url = get_latest_template_version(write_template_url)
        if latest_template_url:
            write_template_url = latest_template_url
            logger.debug(f"Using latest write-role template version: {write_template_url}")
        else:
            logger.warning(
                f"Failed to detect latest write-role template version, using configured URL: {write_template_url}"
            )

        write_launch_url = build_write_role_launch_stack_url(
            template_url=write_template_url,
            region=region,
            external_id=external_id,
            saas_account_id=saas_account_id,
            stack_name=DEFAULT_WRITE_ROLE_STACK_NAME,
        )

    if not read_template_url:
        read_template_url = None
    if not write_template_url:
        write_template_url = None

    return (
        saas_account_id,
        read_launch_url,
        read_template_url,
        write_launch_url,
        write_template_url,
        region if (read_launch_url or write_launch_url) else None,
        DEFAULT_READ_ROLE_STACK_NAME,
        DEFAULT_WRITE_ROLE_STACK_NAME,
        control_plane_template_url,
        control_plane_ingest_url,
        DEFAULT_CONTROL_PLANE_FORWARDER_STACK_NAME,
    )


def is_saas_admin_email(email: str | None) -> bool:
    """Check if user email is allowlisted for SaaS admin access."""
    if not email:
        return False
    return email.strip().lower() in settings.saas_admin_emails_list


async def require_saas_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require an authenticated user whose email is allowlisted as SaaS admin."""
    if not is_saas_admin_email(current_user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SaaS admin access required",
        )
    return current_user
