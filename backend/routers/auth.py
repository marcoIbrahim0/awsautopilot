"""
Auth API endpoints: signup, login, and get current user.
"""
from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import (
    AuthResponse,
    MeResponse,
    create_access_token,
    get_current_user,
    get_saas_and_launch_url,
    hash_password,
    tenant_to_response,
    user_to_response,
    verify_password,
)
from backend.config import settings
from backend.database import get_db
from backend.models.enums import UserRole
from backend.models.tenant import Tenant
from backend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


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


# ============================================
# Endpoints
# ============================================

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
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
        
        # Create tenant with unique external_id
        external_id = f"ext-{uuid.uuid4().hex[:16]}"
        tenant = Tenant(
            name=request.company_name,
            external_id=external_id,
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
        access_token = create_access_token(user.id, tenant.id)
        
        logger.info(f"New signup: tenant={tenant.id}, user={user.id}, email={user.email}")
        
        saas_id, launch_url, template_url, region, default_stack = get_saas_and_launch_url(tenant.external_id)
        return AuthResponse(
            access_token=access_token,
            user=user_to_response(user),
            tenant=tenant_to_response(tenant),
            saas_account_id=saas_id,
            read_role_launch_stack_url=launch_url,
            read_role_template_url=template_url,
            read_role_region=region,
            read_role_default_stack_name=default_stack,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Signup failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Authenticate user and return a JWT token.
    """
    # Find user by email with tenant loaded
    result = await db.execute(
        select(User)
        .options(selectinload(User.tenant))
        .where(User.email == request.email)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Check password
    if not user.password_hash or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Create JWT
    access_token = create_access_token(user.id, user.tenant_id)
    
    logger.info(f"Login: user={user.id}, email={user.email}")
    
    saas_id, launch_url, template_url, region, default_stack = get_saas_and_launch_url(user.tenant.external_id)
    return AuthResponse(
        access_token=access_token,
        user=user_to_response(user),
        tenant=tenant_to_response(user.tenant),
        saas_account_id=saas_id,
        read_role_launch_stack_url=launch_url,
        read_role_template_url=template_url,
        read_role_region=region,
        read_role_default_stack_name=default_stack,
    )


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
    saas_id, launch_url, template_url, region, default_stack = get_saas_and_launch_url(tenant.external_id)
    return MeResponse(
        user=user_to_response(current_user),
        tenant=tenant_to_response(tenant),
        saas_account_id=saas_id,
        read_role_launch_stack_url=launch_url,
        read_role_template_url=template_url,
        read_role_region=region,
        read_role_default_stack_name=default_stack,
    )
