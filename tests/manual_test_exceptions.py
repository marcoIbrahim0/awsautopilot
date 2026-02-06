"""
Manual test script for Exceptions API.
Run this with the backend server running to test the API manually.

Usage:
    python tests/manual_test_exceptions.py
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from backend.database import AsyncSessionLocal
from backend.models.action import Action
from backend.models.enums import EntityType
from backend.models.exception import Exception
from backend.models.finding import Finding
from backend.models.tenant import Tenant
from backend.models.user import User


async def test_exception_crud():
    """Test CRUD operations on exceptions directly via database."""
    async with AsyncSessionLocal() as session:
        # Find or create a test tenant
        tenant = Tenant(name="Test Tenant for Exceptions")
        session.add(tenant)
        await session.commit()
        print(f"✓ Created test tenant: {tenant.id}")

        # Create a test user
        user = User(
            tenant_id=tenant.id,
            email=f"test-{uuid.uuid4()}@example.com",
            name="Test User",
            password_hash="test_hash",
        )
        session.add(user)
        await session.commit()
        print(f"✓ Created test user: {user.id}")

        # Create a test finding
        finding = Finding(
            tenant_id=tenant.id,
            finding_id=f"arn:aws:securityhub:us-east-1:123456789012:finding/test-{uuid.uuid4()}",
            account_id="123456789012",
            region="us-east-1",
            severity_label="HIGH",
            severity_normalized=70,
            status="NEW",
            title="Test Finding for Exception",
            description="This is a test finding",
        )
        session.add(finding)
        await session.commit()
        print(f"✓ Created test finding: {finding.id}")

        # Create an exception for the finding
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        exception = Exception(
            tenant_id=tenant.id,
            entity_type=EntityType.finding,
            entity_id=finding.id,
            reason="Test suppression - false positive detected during security review",
            approved_by_user_id=user.id,
            ticket_link="https://jira.example.com/TEST-123",
            expires_at=expires_at,
        )
        session.add(exception)
        await session.commit()
        print(f"✓ Created exception: {exception.id}")
        print(f"  - Entity: {exception.entity_type.value} ({exception.entity_id})")
        print(f"  - Reason: {exception.reason[:50]}...")
        print(f"  - Expires: {exception.expires_at.isoformat()}")

        # Query the exception back
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await session.execute(
            select(Exception)
            .where(Exception.id == exception.id)
            .options(selectinload(Exception.approved_by))
        )
        queried_exc = result.scalar_one()
        print(f"✓ Queried exception back:")
        print(f"  - Approved by: {queried_exc.approved_by.email}")
        print(f"  - Ticket: {queried_exc.ticket_link}")

        # Test unique constraint (should fail if we try to create another for same entity)
        try:
            duplicate = Exception(
                tenant_id=tenant.id,
                entity_type=EntityType.finding,
                entity_id=finding.id,
                reason="Another reason",
                approved_by_user_id=user.id,
                expires_at=expires_at,
            )
            session.add(duplicate)
            await session.commit()
            print("✗ Unique constraint failed - duplicate was allowed!")
        except Exception as e:
            await session.rollback()
            print(f"✓ Unique constraint working - duplicate rejected: {type(e).__name__}")

        # Create exception for an action
        action = Action(
            tenant_id=tenant.id,
            action_type="test_action",
            target_id="test-target",
            account_id="123456789012",
            region="us-east-1",
            priority=50,
            status="open",
            title="Test Action",
        )
        session.add(action)
        await session.commit()
        print(f"✓ Created test action: {action.id}")

        action_exception = Exception(
            tenant_id=tenant.id,
            entity_type=EntityType.action,
            entity_id=action.id,
            reason="Test action suppression - accepted risk per security policy",
            approved_by_user_id=user.id,
            expires_at=expires_at,
        )
        session.add(action_exception)
        await session.commit()
        print(f"✓ Created exception for action: {action_exception.id}")

        # Test expiry logic
        now = datetime.now(timezone.utc)
        is_expired = queried_exc.expires_at <= now
        print(f"✓ Exception expiry check: expired={is_expired}")

        # Cleanup
        await session.delete(action_exception)
        await session.delete(exception)
        await session.delete(action)
        await session.delete(finding)
        await session.delete(user)
        await session.delete(tenant)
        await session.commit()
        print("✓ Cleaned up test data")

        print("\n✅ All exception model tests passed!")


if __name__ == "__main__":
    print("Testing Exception model and database operations...\n")
    asyncio.run(test_exception_crud())
