#!/usr/bin/env python3
"""
Script to create a tenant in the database.

Usage:
    python scripts/create_tenant.py "Tenant Name"
    python scripts/create_tenant.py "Tenant Name" "custom-external-id"
"""
import asyncio
import sys
import uuid
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.config import settings
from backend.database import async_engine, AsyncSessionLocal
from backend.models.tenant import Tenant
from sqlalchemy.ext.asyncio import create_async_engine


async def create_tenant(name: str, external_id: str | None = None):
    """Create a tenant in the database."""
    # Fix connection string for asyncpg (remove sslmode, asyncpg handles SSL differently)
    db_url = settings.DATABASE_URL
    # Remove sslmode and channel_binding from query string for asyncpg
    if "sslmode=" in db_url:
        # Parse and reconstruct URL without sslmode/channel_binding
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(db_url)
        query_params = parse_qs(parsed.query)
        query_params.pop("sslmode", None)
        query_params.pop("channel_binding", None)
        # For asyncpg with Neon, we need SSL but configured differently
        # Reconstruct URL
        new_query = urlencode(query_params, doseq=True)
        db_url = urlunparse(parsed._replace(query=new_query))
    
    # Create a temporary engine with SSL configured for asyncpg
    import ssl
    engine = create_async_engine(
        db_url,
        connect_args={"ssl": "require"} if "neon" in db_url.lower() else {},
    )
    
    from sqlalchemy.ext.asyncio import async_sessionmaker
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
    
    async with SessionLocal() as db:
        # Generate external_id if not provided
        if not external_id:
            external_id = f"tenant-{uuid.uuid4().hex[:16]}"
        control_plane_token = f"cptok-{uuid.uuid4().hex}"

        # Check if external_id already exists
        from sqlalchemy import select

        result = await db.execute(select(Tenant).where(Tenant.external_id == external_id))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"❌ Tenant with external_id '{external_id}' already exists!")
            print(f"   Tenant ID: {existing.id}")
            print(f"   Tenant Name: {existing.name}")
            return

        # Create new tenant
        tenant = Tenant(
            id=uuid.uuid4(),
            name=name,
            external_id=external_id,
            control_plane_token=control_plane_token,
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

        print("✅ Tenant created successfully!")
        print(f"   Tenant ID: {tenant.id}")
        print(f"   Tenant Name: {tenant.name}")
        print(f"   External ID: {tenant.external_id}")
        print(f"   Control Plane Token: {tenant.control_plane_token}")
        print(f"\n💡 Use this External ID in your CloudFormation stack's ExternalId parameter")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_tenant.py 'Tenant Name' [external_id]")
        print("\nExample:")
        print("  python scripts/create_tenant.py 'Test Company'")
        print("  python scripts/create_tenant.py 'Test Company' 'my-custom-external-id'")
        sys.exit(1)

    tenant_name = sys.argv[1]
    external_id = sys.argv[2] if len(sys.argv) > 2 else None

    asyncio.run(create_tenant(tenant_name, external_id))
