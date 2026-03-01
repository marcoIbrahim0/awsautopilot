"""
Auth API endpoints: signup, login, and get current user.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import (
    AuthResponse,
    MeResponse,
    clear_auth_cookies,
    control_plane_token_fingerprint,
    control_plane_token_response_fields,
    create_access_token,
    generate_control_plane_token,
    generate_password_reset_token,
    get_current_user,
    get_optional_user,
    get_saas_and_launch_url,
    hash_control_plane_token,
    hash_password_reset_token,
    hash_password,
    set_auth_cookies,
    tenant_to_response,
    user_token_version,
    user_to_response,
    verify_password,
)
from backend.config import settings
from backend.database import get_db
from backend.models.audit_log import AuditLog
from backend.models.enums import UserRole
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.services.email import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
RESET_PASSWORD_EXPIRY_MINUTES = 60
FORGOT_PASSWORD_GENERIC_MESSAGE = "If an account exists, a reset link was sent."
_LOGIN_FAILURES: dict[str, list[datetime]] = defaultdict(list)
_LOGIN_FAILURES_LOCK = Lock()


# ============================================
# Request models
# ============================================

class SignupRequest(BaseModel):
    """Request body for signup."""
    company_name: str = Field(..., min_length=1, max_length=255, description="Company/tenant name")
    email: EmailStr = Field(..., description="User email address")
    name: str = Field(..., min_length=1, max_length=255, description="User's full name")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")


class LoginRequest(BaseModel):
    """Request body for login."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, description="One-time reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


class ResetPasswordResponse(BaseModel):
    message: str


class ControlPlaneTokenRotateResponse(BaseModel):
    control_plane_token: str
    control_plane_token_fingerprint: str
    control_plane_token_created_at: str
    control_plane_token_active: bool


class ControlPlaneTokenRevokeResponse(BaseModel):
    control_plane_token_fingerprint: str | None
    control_plane_token_created_at: str | None
    control_plane_token_revoked_at: str
    control_plane_token_active: bool


def _role_value(user: User) -> str:
    role = getattr(user.role, "value", user.role)
    return role if isinstance(role, str) else str(role)


def _require_tenant_admin(user: User) -> None:
    if _role_value(user) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin access required",
        )


async def _get_tenant_for_user(db: AsyncSession, user: User) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def _log_token_event(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    event_type: str,
    summary: str,
) -> None:
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            event_type=event_type,
            entity_type="tenant",
            entity_id=tenant_id,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            summary=summary,
        )
    )


def _issue_access_token(user: User) -> str:
    return create_access_token(
        user.id,
        user.tenant_id,
        token_version=user_token_version(user),
    )


def _invalidate_user_tokens(user: User) -> None:
    user.token_version = user_token_version(user) + 1


def _login_rate_limit_key(email: str, client_host: str | None) -> str:
    normalized_email = (email or "").strip().lower()
    normalized_host = (client_host or "unknown").strip().lower()
    return f"{normalized_email}|{normalized_host}"


def _trim_login_failures(attempts: list[datetime], now: datetime, window_seconds: int) -> None:
    cutoff = now - timedelta(seconds=window_seconds)
    while attempts and attempts[0] < cutoff:
        attempts.pop(0)


def _login_retry_after_seconds(rate_limit_key: str) -> int | None:
    if not settings.AUTH_LOGIN_RATE_LIMIT_ENABLED:
        return None
    max_attempts = max(1, int(settings.AUTH_LOGIN_RATE_LIMIT_MAX_ATTEMPTS or 1))
    window_seconds = max(1, int(settings.AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS or 1))
    now = datetime.now(timezone.utc)
    with _LOGIN_FAILURES_LOCK:
        attempts = _LOGIN_FAILURES.get(rate_limit_key, [])
        _trim_login_failures(attempts, now, window_seconds)
        if len(attempts) < max_attempts:
            if not attempts and rate_limit_key in _LOGIN_FAILURES:
                _LOGIN_FAILURES.pop(rate_limit_key, None)
            return None
        retry_at = attempts[0] + timedelta(seconds=window_seconds)
    return max(1, int((retry_at - now).total_seconds()))


def _record_login_failure(rate_limit_key: str) -> None:
    if not settings.AUTH_LOGIN_RATE_LIMIT_ENABLED:
        return
    window_seconds = max(1, int(settings.AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS or 1))
    now = datetime.now(timezone.utc)
    with _LOGIN_FAILURES_LOCK:
        attempts = _LOGIN_FAILURES.setdefault(rate_limit_key, [])
        _trim_login_failures(attempts, now, window_seconds)
        attempts.append(now)


def _clear_login_failures(rate_limit_key: str) -> None:
    with _LOGIN_FAILURES_LOCK:
        _LOGIN_FAILURES.pop(rate_limit_key, None)


# ============================================
# Endpoints
# ============================================

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Create a new tenant and admin user.
    
    Returns a JWT token that can be used for subsequent authenticated requests.
    The first user of a tenant is always created with role=admin.
    """
    try:
        # Check if email already exists
        result = await db.execute(select(User).where(User.email == request.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        
        # Create tenant with unique external_id + hashed control-plane intake token
        external_id = f"ext-{uuid.uuid4().hex[:16]}"
        control_plane_token = generate_control_plane_token()
        token_created_at = datetime.now(timezone.utc)
        tenant = Tenant(
            name=request.company_name,
            external_id=external_id,
            control_plane_token=hash_control_plane_token(control_plane_token),
            control_plane_token_fingerprint=control_plane_token_fingerprint(control_plane_token),
            control_plane_token_created_at=token_created_at,
            control_plane_token_revoked_at=None,
        )
        db.add(tenant)
        await db.flush()  # Get tenant.id
        
        # Create admin user
        user = User(
            tenant_id=tenant.id,
            email=request.email,
            name=request.name,
            password_hash=hash_password(request.password),
            role=UserRole.admin,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        await db.refresh(tenant)
        
        # Create JWT
        access_token = _issue_access_token(user)
        set_auth_cookies(response, access_token)
        
        logger.info(f"New signup: tenant={tenant.id}, user={user.id}, email={user.email}")
        
        (
            saas_id,
            read_launch_url,
            read_template_url,
            write_launch_url,
            write_template_url,
            region,
            read_default_stack,
            write_default_stack,
            control_plane_template_url,
            control_plane_ingest_url,
            control_plane_default_stack,
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
            control_plane_forwarder_template_url=control_plane_template_url,
            control_plane_ingest_url=control_plane_ingest_url,
            control_plane_forwarder_default_stack_name=control_plane_default_stack,
            **control_plane_token_response_fields(tenant, token_reveal=control_plane_token),
        )
    except HTTPException:
        raise
    except Exception as e:
        correlation_id = uuid.uuid4().hex
        logger.exception("Signup failed [correlation_id=%s]: %s", correlation_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Signup failed. Contact support with correlation_id={correlation_id}.",
        )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Authenticate user and return a JWT token.
    """
    rate_limit_key = _login_rate_limit_key(
        request.email,
        http_request.client.host if http_request.client is not None else None,
    )
    retry_after = _login_retry_after_seconds(rate_limit_key)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    # Find user by email with tenant loaded
    result = await db.execute(
        select(User)
        .options(selectinload(User.tenant))
        .where(User.email == request.email)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        _record_login_failure(rate_limit_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Check password
    if not user.password_hash or not verify_password(request.password, user.password_hash):
        _record_login_failure(rate_limit_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    _clear_login_failures(rate_limit_key)
    
    # Create JWT
    access_token = _issue_access_token(user)
    set_auth_cookies(response, access_token)
    
    logger.info(f"Login: user={user.id}, email={user.email}")
    
    (
        saas_id,
        read_launch_url,
        read_template_url,
        write_launch_url,
        write_template_url,
        region,
        read_default_stack,
        write_default_stack,
        control_plane_template_url,
        control_plane_ingest_url,
        control_plane_default_stack,
    ) = get_saas_and_launch_url(user.tenant.external_id)
    return AuthResponse(
        access_token=access_token,
        user=user_to_response(user),
        tenant=tenant_to_response(user.tenant),
        saas_account_id=saas_id,
        read_role_launch_stack_url=read_launch_url,
        read_role_template_url=read_template_url,
        read_role_region=region,
        read_role_default_stack_name=read_default_stack,
        write_role_launch_stack_url=write_launch_url,
        write_role_template_url=write_template_url,
        write_role_default_stack_name=write_default_stack,
        control_plane_forwarder_template_url=control_plane_template_url,
        control_plane_ingest_url=control_plane_ingest_url,
        control_plane_forwarder_default_stack_name=control_plane_default_stack,
        **(
            control_plane_token_response_fields(user.tenant, token_reveal=None)
            if _role_value(user) == "admin"
            else {}
        ),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_auth(
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
) -> RefreshResponse:
    """
    Refresh authenticated session and issue a new access token.
    """
    access_token = _issue_access_token(current_user)
    set_auth_cookies(response, access_token)
    return RefreshResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    current_user: Annotated[User | None, Depends(get_optional_user)] = None,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Clear browser auth/CSRF cookies and invalidate current server-side token lineage.
    """
    if current_user is not None:
        _invalidate_user_tokens(current_user)
        await db.commit()
    clear_auth_cookies(response)


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: PasswordChangeRequest,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Change current user's password and invalidate previously issued tokens.
    """
    if not current_user.password_hash or not verify_password(request.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect",
        )
    current_user.password_hash = hash_password(request.new_password)
    current_user.password_reset_token_hash = None
    current_user.password_reset_expires_at = None
    current_user.password_reset_requested_at = None
    _invalidate_user_tokens(current_user)
    await db.commit()

    access_token = _issue_access_token(current_user)
    set_auth_cookies(response, access_token)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    """
    Request a password reset link. Always returns a generic success response.
    """
    generic = ForgotPasswordResponse(message=FORGOT_PASSWORD_GENERIC_MESSAGE)
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    if user is None:
        return generic

    reset_token = generate_password_reset_token()
    now = datetime.now(timezone.utc)
    user.password_reset_token_hash = hash_password_reset_token(reset_token)
    user.password_reset_requested_at = now
    user.password_reset_expires_at = now + timedelta(minutes=RESET_PASSWORD_EXPIRY_MINUTES)
    await db.commit()

    email_service.send_password_reset_email(
        to_email=user.email,
        reset_token=reset_token,
    )
    return generic


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordResponse:
    """
    Reset password using a one-time token.
    """
    token_hash = hash_password_reset_token(request.token)
    result = await db.execute(
        select(User).where(User.password_reset_token_hash == token_hash)
    )
    user = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if user is None or user.password_reset_expires_at is None or user.password_reset_expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    user.password_hash = hash_password(request.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.password_reset_requested_at = None
    _invalidate_user_tokens(user)
    await db.commit()

    return ResetPasswordResponse(message="Password reset successful.")


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> MeResponse:
    """
    Get current authenticated user and their tenant.
    
    Response includes:
    - user: id, email, name, role, onboarding_completed_at
    - tenant: id, name, external_id (for CloudFormation/Settings display)
    - saas_account_id: SaaS AWS account ID (for Launch Stack params)
    - read_role_launch_stack_url: one-click deploy link when template URL is configured
    """
    tenant = current_user.tenant
    (
        saas_id,
        read_launch_url,
        read_template_url,
        write_launch_url,
        write_template_url,
        region,
        read_default_stack,
        write_default_stack,
        control_plane_template_url,
        control_plane_ingest_url,
        control_plane_default_stack,
    ) = get_saas_and_launch_url(tenant.external_id)
    return MeResponse(
        user=user_to_response(current_user),
        tenant=tenant_to_response(tenant),
        saas_account_id=saas_id,
        read_role_launch_stack_url=read_launch_url,
        read_role_template_url=read_template_url,
        read_role_region=region,
        read_role_default_stack_name=read_default_stack,
        write_role_launch_stack_url=write_launch_url,
        write_role_template_url=write_template_url,
        write_role_default_stack_name=write_default_stack,
        control_plane_forwarder_template_url=control_plane_template_url,
        control_plane_ingest_url=control_plane_ingest_url,
        control_plane_forwarder_default_stack_name=control_plane_default_stack,
        **(
            control_plane_token_response_fields(tenant, token_reveal=None)
            if _role_value(current_user) == "admin"
            else {}
        ),
    )


@router.post("/control-plane-token/rotate", response_model=ControlPlaneTokenRotateResponse)
async def rotate_control_plane_token(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ControlPlaneTokenRotateResponse:
    """Rotate tenant control-plane token and reveal it exactly once."""
    _require_tenant_admin(current_user)
    tenant = await _get_tenant_for_user(db, current_user)
    new_token = generate_control_plane_token()
    now = datetime.now(timezone.utc)
    old_fingerprint = tenant.control_plane_token_fingerprint
    tenant.control_plane_token = hash_control_plane_token(new_token)
    tenant.control_plane_token_fingerprint = control_plane_token_fingerprint(new_token)
    tenant.control_plane_token_created_at = now
    tenant.control_plane_token_revoked_at = None
    _log_token_event(
        db,
        tenant_id=tenant.id,
        user_id=current_user.id,
        event_type="control_plane_token_rotated",
        summary=f"Rotated control-plane token ({old_fingerprint} -> {tenant.control_plane_token_fingerprint}).",
    )
    await db.commit()
    await db.refresh(tenant)
    return ControlPlaneTokenRotateResponse(
        control_plane_token=new_token,
        control_plane_token_fingerprint=tenant.control_plane_token_fingerprint,
        control_plane_token_created_at=tenant.control_plane_token_created_at.isoformat(),
        control_plane_token_active=True,
    )


@router.post("/control-plane-token/revoke", response_model=ControlPlaneTokenRevokeResponse)
async def revoke_control_plane_token(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ControlPlaneTokenRevokeResponse:
    """Revoke tenant control-plane token without revealing any token value."""
    _require_tenant_admin(current_user)
    tenant = await _get_tenant_for_user(db, current_user)
    revoked_at = tenant.control_plane_token_revoked_at or datetime.now(timezone.utc)
    if tenant.control_plane_token_revoked_at is None:
        tenant.control_plane_token_revoked_at = revoked_at
        _log_token_event(
            db,
            tenant_id=tenant.id,
            user_id=current_user.id,
            event_type="control_plane_token_revoked",
            summary=f"Revoked control-plane token ({tenant.control_plane_token_fingerprint}).",
        )
        await db.commit()
        await db.refresh(tenant)
    return ControlPlaneTokenRevokeResponse(
        control_plane_token_fingerprint=tenant.control_plane_token_fingerprint,
        control_plane_token_created_at=(
            tenant.control_plane_token_created_at.isoformat() if tenant.control_plane_token_created_at else None
        ),
        control_plane_token_revoked_at=revoked_at.isoformat(),
        control_plane_token_active=False,
    )
