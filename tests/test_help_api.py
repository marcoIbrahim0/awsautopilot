from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.auth import get_current_user, require_saas_admin
from backend.database import get_db
from backend.main import app
from backend.models.help_assistant_interaction import HelpAssistantInteraction
from backend.services.help_assistant import (
    HelpAssistantCitation,
    HelpAssistantRunResult,
    HelpAssistantStructuredResult,
    HelpAssistantUsage,
)

NOW = datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)


def _article(
    *,
    slug: str = "connect-and-validate-aws",
    title: str = "Connect and Validate AWS",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        slug=slug,
        title=title,
        summary="Use onboarding to validate the account connection and service readiness.",
        body="Full article body",
        audience="customer",
        published=True,
        sort_order=1,
        tags=["onboarding", "aws_connection"],
        related_routes=["/onboarding", "/accounts"],
        created_at=NOW,
        updated_at=NOW,
    )


def _user(*, email: str, tenant_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        email=email,
    )


def _attachment(
    *,
    message_id: uuid.UUID,
    internal_only: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        message_id=message_id,
        filename="evidence.txt",
        content_type="text/plain",
        size_bytes=128,
        internal_only=internal_only,
        created_at=NOW,
        uploaded_at=NOW,
    )


def _message(
    *,
    author: SimpleNamespace,
    role: str,
    body: str,
    internal_only: bool = False,
) -> SimpleNamespace:
    message_id = uuid.uuid4()
    return SimpleNamespace(
        id=message_id,
        role=role,
        body=body,
        internal_only=internal_only,
        created_by_user_id=author.id,
        created_by=author,
        created_at=NOW,
        attachments=[_attachment(message_id=message_id, internal_only=internal_only)],
    )


def _case(
    *,
    requester: SimpleNamespace,
    assignee: SimpleNamespace | None = None,
    status: str = "triaging",
    last_message_at: datetime = NOW,
    messages: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    messages = messages or []
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=requester.tenant_id,
        requester_user_id=requester.id,
        requester=requester,
        assigned_saas_admin_user_id=assignee.id if assignee else None,
        assignee=assignee,
        subject="Need help with onboarding validation",
        category="onboarding",
        priority="normal",
        status=status,
        source="manual",
        current_path="/onboarding",
        referenced_entities=[{"type": "route", "id": "/onboarding"}],
        first_response_at=None,
        resolved_at=None,
        closed_at=None,
        last_message_at=last_message_at,
        created_at=NOW,
        updated_at=NOW,
        messages=messages,
        attachments=[attachment for message in messages for attachment in message.attachments],
    )


def _session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _interaction_session() -> MagicMock:
    session = _session()

    def _add(item: object) -> None:
        if isinstance(item, HelpAssistantInteraction):
            item.id = uuid.UUID("223e4567-e89b-12d3-a456-426614174000")
            item.thread_id = uuid.UUID("323e4567-e89b-12d3-a456-426614174000")

    session.add.side_effect = _add
    return session


def test_help_articles_public_list_returns_published_articles() -> None:
    session = _session()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with patch(
            "backend.routers.help.list_help_articles",
            new=AsyncMock(return_value=[_article()]),
        ):
            client = TestClient(app)
            response = client.get("/api/help/articles")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["slug"] == "connect-and-validate-aws"


def test_customer_help_case_detail_hides_internal_support_notes() -> None:
    requester = _user(email="requester@example.com")
    support = _user(email="support@example.com", tenant_id=requester.tenant_id)
    case = _case(
        requester=requester,
        messages=[
            _message(author=requester, role="requester", body="Initial request"),
            _message(author=support, role="support", body="Internal triage note", internal_only=True),
        ],
    )
    session = _session()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> SimpleNamespace:
        return requester

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with patch(
            "backend.routers.help.get_customer_case_or_404",
            new=AsyncMock(return_value=case),
        ):
            client = TestClient(app)
            response = client.get(f"/api/help/cases/{case.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["body"] == "Initial request"


def test_customer_help_case_detail_returns_404_for_other_requester() -> None:
    requester = _user(email="requester@example.com")
    session = _session()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> SimpleNamespace:
        return requester

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with patch(
            "backend.routers.help.get_customer_case_or_404",
            new=AsyncMock(side_effect=HTTPException(status_code=404, detail="Help case not found")),
        ):
            client = TestClient(app)
            response = client.get(f"/api/help/cases/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404


def test_admin_help_case_detail_includes_internal_support_notes() -> None:
    requester = _user(email="requester@example.com")
    admin = _user(email="admin@example.com", tenant_id=requester.tenant_id)
    case = _case(
        requester=requester,
        assignee=admin,
        messages=[
            _message(author=requester, role="requester", body="Initial request"),
            _message(author=admin, role="support", body="Internal triage note", internal_only=True),
        ],
    )
    session = _session()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_require_saas_admin() -> SimpleNamespace:
        return admin

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[require_saas_admin] = _override_require_saas_admin
    try:
        with patch(
            "backend.routers.help.get_admin_case_or_404",
            new=AsyncMock(return_value=case),
        ):
            client = TestClient(app)
            response = client.get(f"/api/saas/help/cases/{case.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_saas_admin, None)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["messages"]) == 2
    assert payload["messages"][1]["internal_only"] is True


def test_help_assistant_query_escalates_to_case_when_support_is_needed() -> None:
    requester = _user(email="requester@example.com")
    case = _case(
        requester=requester,
        messages=[_message(author=requester, role="requester", body="Need human help")],
    )
    session = _interaction_session()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> SimpleNamespace:
        return requester

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with patch(
            "backend.routers.help.build_help_context",
            new=AsyncMock(return_value={"referenced_entities": [{"type": "route", "id": "/actions/123"}]}),
        ), patch(
            "backend.routers.help.search_help_articles",
            new=AsyncMock(return_value=[]),
        ), patch(
            "backend.routers.help.list_thread_history",
            new=AsyncMock(return_value=[]),
        ), patch(
            "backend.routers.help.generate_help_assistant_answer",
            return_value=HelpAssistantRunResult(
                result=HelpAssistantStructuredResult(
                    answer="I could not answer this confidently. I escalated it to support.",
                    confidence="low",
                    suggested_case=True,
                    citations=[
                        HelpAssistantCitation(
                            slug="when-to-contact-support",
                            title="When to Contact Support",
                            summary="Escalation guidance",
                        )
                    ],
                    follow_up_questions=[],
                    context_gaps=["Missing matching article evidence."],
                ),
                provider_name="openai",
                model_name="gpt-5-mini",
                reasoning_effort="low",
                usage=HelpAssistantUsage(input_tokens=10, output_tokens=5, total_tokens=15),
                response_payload={"id": "resp_123"},
                latency_ms=200,
                error_code=None,
            ),
        ), patch(
            "backend.routers.help._create_case",
            new=AsyncMock(return_value=case),
        ) as mock_create_case, patch(
            "backend.routers.help.create_help_case_notification",
            new=AsyncMock(),
        ), patch(
            "backend.routers.help.send_help_case_admin_email",
        ) as mock_send_email:
            client = TestClient(app)
            response = client.post(
                "/api/help/assistant/query",
                json={
                    "question": "I need human help with this action.",
                    "current_path": "/actions/123",
                    "action_id": "123",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["thread_id"] == "323e4567-e89b-12d3-a456-426614174000"
    assert payload["confidence"] == "low"
    assert payload["suggested_case"] is True
    assert payload["escalated_case_id"] == str(case.id)
    assert mock_create_case.await_args.kwargs["source"] == "ai_escalation"
    mock_send_email.assert_called_once()


def test_help_assistant_thread_returns_turns_for_requester() -> None:
    requester = _user(email="requester@example.com")
    interaction = SimpleNamespace(
        id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        question="How do I validate my account?",
        response_text="Use the onboarding flow and review validation warnings.",
        confidence="medium",
        suggested_case=False,
        citations=[{"slug": "connect-and-validate-aws", "title": "Connect and Validate AWS", "summary": "Validation guide"}],
        cited_article_slugs=["connect-and-validate-aws"],
        follow_up_questions=["What should I do if validation fails?"],
        context_gaps=[],
        helpful=None,
        feedback_text=None,
        created_at=NOW,
        escalated_case_id=None,
        current_path="/onboarding",
    )
    session = _session()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_get_current_user() -> SimpleNamespace:
        return requester

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with patch(
            "backend.routers.help.get_help_thread",
            new=AsyncMock(return_value=SimpleNamespace(thread_id=str(interaction.thread_id), current_path="/onboarding", turns=[])),
        ), patch(
            "backend.routers.help.serialize_help_thread",
            return_value={
                "thread_id": str(interaction.thread_id),
                "current_path": "/onboarding",
                "turns": [
                    {
                        "interaction_id": str(interaction.id),
                        "question": interaction.question,
                        "answer": interaction.response_text,
                        "confidence": interaction.confidence,
                        "suggested_case": interaction.suggested_case,
                        "citations": interaction.citations,
                        "follow_up_questions": interaction.follow_up_questions,
                        "context_gaps": interaction.context_gaps,
                        "helpful": interaction.helpful,
                        "feedback_text": interaction.feedback_text,
                        "created_at": interaction.created_at.isoformat(),
                        "escalated_case_id": None,
                    }
                ],
            },
        ):
            client = TestClient(app)
            response = client.get(f"/api/help/assistant/threads/{interaction.thread_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["thread_id"] == str(interaction.thread_id)
    assert payload["turns"][0]["question"] == interaction.question


def test_admin_help_cases_support_sla_state_filter() -> None:
    admin = _user(email="admin@example.com")
    requester = _user(email="requester@example.com")
    now = datetime.now(timezone.utc)
    overdue_case = _case(
        requester=requester,
        assignee=admin,
        last_message_at=now - timedelta(hours=30),
    )
    active_case = _case(
        requester=requester,
        assignee=admin,
        last_message_at=now - timedelta(hours=1),
    )
    session = _session()

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def _override_require_saas_admin() -> SimpleNamespace:
        return admin

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[require_saas_admin] = _override_require_saas_admin
    try:
        with patch(
            "backend.routers.help.list_admin_cases",
            new=AsyncMock(return_value=[overdue_case, active_case]),
        ):
            client = TestClient(app)
            response = client.get("/api/saas/help/cases?sla_state=overdue")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_saas_admin, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == str(overdue_case.id)
