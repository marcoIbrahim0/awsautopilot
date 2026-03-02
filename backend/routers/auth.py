"""
Auth API endpoints: signup, login, and get current user.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Annotated, Literal

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
SECURITY_CODE_EXPIRY_MINUTES = 10
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


class SendVerificationRequest(BaseModel):
    verification_type: Literal["email", "phone"] = Field(..., description="Verification channel type")


class SendVerificationResponse(BaseModel):
    message: str
    debug_code: str | None = None


class ConfirmVerificationRequest(BaseModel):
    verification_type: Literal["email", "phone"] = Field(..., description="Verification channel type")
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$", description="6-digit verification code")


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


class MfaChallengeResponse(BaseModel):
    mfa_required: bool = True
    mfa_ticket: str
    mfa_method: Literal["email", "phone"]
    destination_hint: str


class LoginMfaRequest(BaseModel):
    mfa_ticket: str = Field(..., min_length=1, max_length=512, description="MFA challenge ticket returned by login")
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$", description="6-digit MFA code")


class MfaSettingsResponse(BaseModel):
    mfa_enabled: bool
    mfa_method: Literal["email", "phone"] | None = None
    email_verified: bool
    phone_verified: bool
    phone_number: str | None = None


class UpdateMfaSettingsRequest(BaseModel):
    mfa_enabled: bool
    mfa_method: Literal["email", "phone"] | None = None


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


def _hash_security_token(token: str) -> str:
    normalized = (token or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _generate_security_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _generate_mfa_ticket() -> str:
    return secrets.token_urlsafe(32)


def _mask_email(email: str) -> str:
    normalized = (email or "").strip()
    if "@" not in normalized:
        return "***"
    local, _, domain = normalized.partition("@")
    if len(local) <= 2:
        return f"{local[:1]}***@{domain}"
    return f"{local[:2]}***@{domain}"


def _mask_phone(phone: str) -> str:
    normalized = (phone or "").strip()
    digits = "".join(ch for ch in normalized if ch.isdigit())
    if not digits:
        return "***"
    if len(digits) <= 4:
        return f"***{digits}"
    return f"***{digits[-4:]}"


def _clear_mfa_challenge(user: User) -> None:
    user.mfa_challenge_code_hash = None
    user.mfa_challenge_token_hash = None
    user.mfa_challenge_expires_at = None


def _mfa_settings_response(user: User) -> MfaSettingsResponse:
    method = (getattr(user, "mfa_method", None) or None)
    typed_method: Literal["email", "phone"] | None = method if method in {"email", "phone"} else None
    return MfaSettingsResponse(
        mfa_enabled=bool(getattr(user, "mfa_enabled", False)),
        mfa_method=typed_method,
        email_verified=bool(getattr(user, "email_verified", False)),
        phone_verified=bool(getattr(user, "phone_verified", False)),
        phone_number=getattr(user, "phone_number", None),
    )


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


@router.post("/login", response_model=AuthResponse | MfaChallengeResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse | MfaChallengeResponse:
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

    mfa_enabled = bool(getattr(user, "mfa_enabled", False))
    mfa_method = ((getattr(user, "mfa_method", "") or "").strip().lower())
    if mfa_enabled:
        if mfa_method not in {"email", "phone"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is enabled but misconfigured. Update MFA settings.",
            )

        code = _generate_security_code()
        ticket = _generate_mfa_ticket()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=SECURITY_CODE_EXPIRY_MINUTES)

        if mfa_method == "email":
            delivered = email_service.send_security_code_email(
                to_email=user.email,
                code=code,
                purpose="multi-factor authentication",
            )
            destination_hint = _mask_email(user.email)
        else:
            phone_number = (getattr(user, "phone_number", None) or "").strip()
            if not phone_number:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MFA requires a verified phone number.",
                )
            delivered = email_service.send_phone_security_code(
                to_phone=phone_number,
                code=code,
                purpose="multi-factor authentication",
                fallback_email=user.email,
            )
            destination_hint = _mask_phone(phone_number)

        if not delivered:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to deliver MFA code. Please try again.",
            )

        user.mfa_challenge_code_hash = _hash_security_token(code)
        user.mfa_challenge_token_hash = _hash_security_token(ticket)
        user.mfa_challenge_expires_at = expires_at
        await db.commit()
        logger.info("MFA challenge issued for user=%s method=%s", user.id, mfa_method)
        return MfaChallengeResponse(
            mfa_required=True,
            mfa_ticket=ticket,
            mfa_method="phone" if mfa_method == "phone" else "email",
            destination_hint=destination_hint,
        )
    
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


@router.post("/login/mfa", response_model=AuthResponse)
async def login_with_mfa(
    request: LoginMfaRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Complete MFA login by validating challenge ticket + code and issuing access token."""
    ticket_hash = _hash_security_token(request.mfa_ticket)
    result = await db.execute(
        select(User)
        .options(selectinload(User.tenant))
        .where(User.mfa_challenge_token_hash == ticket_hash)
    )
    user = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if (
        user is None
        or not getattr(user, "mfa_challenge_expires_at", None)
        or user.mfa_challenge_expires_at < now
        or not getattr(user, "mfa_challenge_code_hash", None)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA challenge",
        )

    if _hash_security_token(request.code) != user.mfa_challenge_code_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code",
        )

    _clear_mfa_challenge(user)
    await db.commit()

    access_token = _issue_access_token(user)
    set_auth_cookies(response, access_token)

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


@router.post("/verify/send", response_model=SendVerificationResponse)
async def send_verification_code(
    request: SendVerificationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> SendVerificationResponse:
    """Send a verification code to the current user's email or phone."""
    code = _generate_security_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=SECURITY_CODE_EXPIRY_MINUTES)
    verification_type = request.verification_type

    if verification_type == "email":
        delivered = email_service.send_security_code_email(
            to_email=current_user.email,
            code=code,
            purpose="email verification",
        )
        if not delivered:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to deliver verification code.",
            )
        current_user.email_verification_code_hash = _hash_security_token(code)
        current_user.email_verification_expires_at = expires_at
    else:
        phone_number = (getattr(current_user, "phone_number", None) or "").strip()
        if not phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Add a phone number before requesting phone verification.",
            )
        delivered = email_service.send_phone_security_code(
            to_phone=phone_number,
            code=code,
            purpose="phone verification",
            fallback_email=current_user.email,
        )
        if not delivered:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to deliver verification code.",
            )
        current_user.phone_verification_code_hash = _hash_security_token(code)
        current_user.phone_verification_expires_at = expires_at

    await db.commit()
    local_mode_message = (
        "Local mode: email/SMS delivery is disabled. Use the 6-digit debug code shown below."
    )
    return SendVerificationResponse(
        message=local_mode_message if settings.is_local else f"A 6-digit code has been sent to your {verification_type}.",
        debug_code=code if settings.is_local else None,
    )


@router.post("/verify/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_verification_code(
    request: ConfirmVerificationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Confirm verification code for email or phone."""
    now = datetime.now(timezone.utc)
    if request.verification_type == "email":
        expected_hash = getattr(current_user, "email_verification_code_hash", None)
        expires_at = getattr(current_user, "email_verification_expires_at", None)
        if not expected_hash or not expires_at or expires_at < now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")
        if _hash_security_token(request.code) != expected_hash:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")
        current_user.email_verified = True
        current_user.email_verification_code_hash = None
        current_user.email_verification_expires_at = None
    else:
        expected_hash = getattr(current_user, "phone_verification_code_hash", None)
        expires_at = getattr(current_user, "phone_verification_expires_at", None)
        phone_number = (getattr(current_user, "phone_number", None) or "").strip()
        if not phone_number:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No phone number found on account")
        if not expected_hash or not expires_at or expires_at < now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")
        if _hash_security_token(request.code) != expected_hash:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")
        current_user.phone_verified = True
        current_user.phone_verification_code_hash = None
        current_user.phone_verification_expires_at = None

    await db.commit()


@router.get("/mfa/settings", response_model=MfaSettingsResponse)
async def get_mfa_settings(
    current_user: Annotated[User, Depends(get_current_user)],
) -> MfaSettingsResponse:
    """Return MFA status for the current user."""
    return _mfa_settings_response(current_user)


@router.patch("/mfa/settings", response_model=MfaSettingsResponse)
async def update_mfa_settings(
    request: UpdateMfaSettingsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> MfaSettingsResponse:
    """Enable or disable MFA for the current user."""
    if not request.mfa_enabled:
        current_user.mfa_enabled = False
        current_user.mfa_method = None
        _clear_mfa_challenge(current_user)
        await db.commit()
        await db.refresh(current_user)
        return _mfa_settings_response(current_user)

    method = (request.mfa_method or getattr(current_user, "mfa_method", None) or "email").strip().lower()
    if method not in {"email", "phone"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mfa_method must be 'email' or 'phone'")

    if method == "email":
        if not bool(getattr(current_user, "email_verified", False)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verify your email before enabling email-based MFA.",
            )
    else:
        if not bool(getattr(current_user, "phone_verified", False)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verify your phone before enabling phone-based MFA.",
            )
        if not (getattr(current_user, "phone_number", None) or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A phone number is required for phone-based MFA.",
            )

    current_user.mfa_enabled = True
    current_user.mfa_method = method
    await db.commit()
    await db.refresh(current_user)
    return _mfa_settings_response(current_user)


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
