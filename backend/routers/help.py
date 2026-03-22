from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any
from dataclasses import asdict

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Path, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user, is_saas_admin_email, require_saas_admin
from backend.database import get_db
from backend.models.audit_log import AuditLog
from backend.models.help_assistant_interaction import HelpAssistantInteraction
from backend.models.help_case import HelpCase
from backend.models.help_case_message import HelpCaseMessage
from backend.models.user import User
from backend.services.help_assistant import (
    build_system_answer,
    generate_help_assistant_answer,
    get_help_thread,
    list_thread_history,
    serialize_help_thread,
)
from backend.services.help_cases import (
    compute_help_case_sla_state,
    count_admin_cases,
    get_admin_case_or_404,
    get_customer_case_or_404,
    list_admin_cases,
    list_customer_cases,
    serialize_help_case,
    serialize_help_case_attachment,
    validate_case_category,
    validate_case_priority,
    validate_case_source,
    validate_case_status,
)
from backend.services.help_center import (
    get_help_article_by_slug,
    list_help_articles,
    search_help_articles,
    serialize_help_article,
    serialize_help_match,
)
from backend.services.help_context import build_help_context
from backend.services.help_live_iam import (
    build_ingested_security_references,
    resolve_live_lookup_state,
    run_live_iam_lookup,
)
from backend.services.help_notifications import (
    create_help_case_notification,
    send_help_case_admin_email,
    send_help_case_requester_email,
)
from backend.services.help_storage import build_case_attachment_download_url, upload_case_attachment

router = APIRouter(prefix="/help", tags=["help"])
saas_router = APIRouter(prefix="/saas/help", tags=["saas-help"])


class HelpArticleResponse(BaseModel):
    id: str
    slug: str
    title: str
    summary: str
    body: str
    audience: str
    published: bool
    sort_order: int
    tags: list[str]
    related_routes: list[str]
    created_at: str
    updated_at: str | None


class HelpSearchResultResponse(HelpArticleResponse):
    score: int
    snippet: str


class HelpAttachmentResponse(BaseModel):
    id: str
    message_id: str
    filename: str
    content_type: str | None
    size_bytes: int | None
    internal_only: bool
    created_at: str
    uploaded_at: str | None


class HelpMessageResponse(BaseModel):
    id: str
    role: str
    body: str
    internal_only: bool
    created_by_user_id: str | None
    created_by_email: str | None
    created_at: str
    attachments: list[HelpAttachmentResponse]


class HelpCaseResponse(BaseModel):
    id: str
    tenant_id: str
    requester_user_id: str
    requester_email: str | None
    assigned_saas_admin_user_id: str | None
    assigned_saas_admin_email: str | None
    subject: str
    category: str
    priority: str
    status: str
    source: str
    current_path: str | None
    referenced_entities: list[dict[str, str]]
    first_response_at: str | None
    resolved_at: str | None
    closed_at: str | None
    last_message_at: str | None
    created_at: str
    updated_at: str | None
    sla_state: str
    messages: list[HelpMessageResponse]


class HelpCaseListResponse(BaseModel):
    items: list[HelpCaseResponse]
    total: int


class HelpArticleListResponse(BaseModel):
    items: list[HelpArticleResponse]
    total: int


class HelpSearchResponse(BaseModel):
    items: list[HelpSearchResultResponse]
    total: int


class HelpAssistantRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    thread_id: str | None = Field(default=None, max_length=64)
    current_path: str | None = Field(default=None, max_length=500)
    account_id: str | None = Field(default=None, max_length=32)
    action_id: str | None = Field(default=None, max_length=64)
    finding_id: str | None = Field(default=None, max_length=64)
    request_human: bool = False
    confirm_live_lookup: bool = False


class HelpAssistantFeedbackRequest(BaseModel):
    helpful: bool | None = None
    feedback_text: str | None = Field(default=None, max_length=4000)


class HelpAssistantResponse(BaseModel):
    thread_id: str
    interaction_id: str
    answer: str
    confidence: str
    suggested_case: bool
    citations: list[dict[str, str]]
    follow_up_questions: list[str] = Field(default_factory=list)
    context_gaps: list[str] = Field(default_factory=list)
    escalated_case_id: str | None = None
    live_lookup: dict[str, Any] | None = None


class HelpAssistantTurnResponse(BaseModel):
    interaction_id: str
    question: str
    answer: str
    confidence: str
    suggested_case: bool
    citations: list[dict[str, str]]
    follow_up_questions: list[str]
    context_gaps: list[str]
    helpful: bool | None = None
    feedback_text: str | None = None
    created_at: str
    escalated_case_id: str | None = None
    live_lookup: dict[str, Any] | None = None


class HelpAssistantThreadResponse(BaseModel):
    thread_id: str
    current_path: str | None = None
    turns: list[HelpAssistantTurnResponse]


class HelpCaseCreateRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=64)
    priority: str | None = Field(default="normal", max_length=32)
    body: str = Field(..., min_length=1, max_length=10000)
    source: str = Field(default="manual", min_length=1, max_length=32)
    current_path: str | None = Field(default=None, max_length=500)
    account_id: str | None = Field(default=None, max_length=32)
    action_id: str | None = Field(default=None, max_length=64)
    finding_id: str | None = Field(default=None, max_length=64)


class HelpCaseMessageCreateRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)


class HelpCaseUpdateRequest(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    priority: str | None = Field(default=None, max_length=32)
    assigned_saas_admin_user_id: str | None = Field(default=None, max_length=64)


class HelpAttachmentDownloadResponse(BaseModel):
    download_url: str


def _serialize_case_payload(case: HelpCase, *, include_internal: bool) -> HelpCaseResponse:
    return HelpCaseResponse.model_validate(serialize_help_case(case, include_internal=include_internal))


def _record_audit(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    entity_id: uuid.UUID,
    event_type: str,
    summary: str,
) -> None:
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            event_type=event_type,
            entity_type="help_case",
            entity_id=entity_id,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            summary=summary,
        )
    )


def _help_subject(question: str) -> str:
    compact = " ".join(question.strip().split())
    if len(compact) <= 120:
        return compact
    return f"{compact[:117]}..."


def _interaction_live_lookup(interaction: HelpAssistantInteraction) -> dict[str, Any] | None:
    if not isinstance(interaction.response_payload, dict):
        return None
    return interaction.response_payload.get("live_lookup")


def _assistant_response(interaction: HelpAssistantInteraction) -> HelpAssistantResponse:
    return HelpAssistantResponse(
        thread_id=str(interaction.thread_id),
        interaction_id=str(interaction.id),
        answer=interaction.response_text,
        confidence=interaction.confidence,
        suggested_case=bool(interaction.suggested_case),
        citations=list(interaction.citations or []),
        follow_up_questions=list(interaction.follow_up_questions or []),
        context_gaps=list(interaction.context_gaps or []),
        escalated_case_id=str(interaction.escalated_case_id) if interaction.escalated_case_id else None,
        live_lookup=_interaction_live_lookup(interaction),
    )


def _parse_optional_thread_id(thread_id: str | None) -> uuid.UUID | None:
    if not thread_id:
        return None
    try:
        return uuid.UUID(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="thread_id must be a valid UUID") from exc


def _assistant_case_message(
    *,
    history: list[HelpAssistantInteraction],
    answer_text: str,
    citations: list[dict[str, str]],
    context_gaps: list[str],
) -> str:
    lines = ["AI assistant summary:", answer_text]
    if history:
        lines.append("")
        lines.append("Recent thread:")
        for turn in history[-2:]:
            lines.append(f"- User: {turn.question}")
            lines.append(f"- Assistant: {turn.response_text}")
    if citations:
        lines.append("")
        lines.append("Cited articles: " + ", ".join(item["slug"] for item in citations))
    if context_gaps:
        lines.append("Context gaps: " + " ".join(context_gaps))
    return "\n".join(lines)


async def _create_case(
    db: AsyncSession,
    *,
    current_user: User,
    subject: str,
    category: str,
    priority: str,
    source: str,
    body: str,
    current_path: str | None,
    referenced_entities: list[dict[str, str]],
    include_assistant_message: str | None = None,
) -> HelpCase:
    now = datetime.now(timezone.utc)
    case = HelpCase(
        tenant_id=current_user.tenant_id,
        requester_user_id=current_user.id,
        subject=subject,
        category=validate_case_category(category),
        priority=validate_case_priority(priority),
        status="new",
        source=validate_case_source(source),
        current_path=current_path,
        referenced_entities=referenced_entities,
        last_message_at=now,
    )
    db.add(case)
    await db.flush()
    db.add(
        HelpCaseMessage(
            case_id=case.id,
            tenant_id=current_user.tenant_id,
            created_by_user_id=current_user.id,
            role="requester",
            body=body.strip(),
            internal_only=False,
        )
    )
    if include_assistant_message:
        db.add(
            HelpCaseMessage(
                case_id=case.id,
                tenant_id=current_user.tenant_id,
                created_by_user_id=current_user.id,
                role="assistant",
                body=include_assistant_message,
                internal_only=False,
            )
        )
    _record_audit(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_id=case.id,
        event_type="help_case_created",
        summary=f"Help case created: {case.subject}",
    )
    await db.flush()
    return case


async def _maybe_assign_admin(
    db: AsyncSession,
    *,
    case: HelpCase,
    assigned_saas_admin_user_id: str | None,
) -> None:
    if assigned_saas_admin_user_id is None:
        return
    if not assigned_saas_admin_user_id:
        case.assigned_saas_admin_user_id = None
        return
    try:
        assignee_uuid = uuid.UUID(assigned_saas_admin_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="assigned_saas_admin_user_id must be a valid UUID") from exc
    result = await db.execute(select(User).where(User.id == assignee_uuid))
    assignee = result.scalar_one_or_none()
    if assignee is None or not is_saas_admin_email(assignee.email):
        raise HTTPException(status_code=400, detail="Assigned user must be a SaaS admin")
    case.assigned_saas_admin_user_id = assignee.id


async def _admin_reply_case(
    db: AsyncSession,
    *,
    admin: User,
    case: HelpCase,
    body: str,
    internal_only: bool,
) -> HelpCaseMessage:
    now = datetime.now(timezone.utc)
    message = HelpCaseMessage(
        case_id=case.id,
        tenant_id=case.tenant_id,
        created_by_user_id=admin.id,
        role="support",
        body=body.strip(),
        internal_only=internal_only,
    )
    case.last_message_at = now
    if not internal_only:
        case.first_response_at = case.first_response_at or now
        case.status = "waiting_on_customer"
    db.add(message)
    _record_audit(
        db,
        tenant_id=case.tenant_id,
        user_id=admin.id,
        entity_id=case.id,
        event_type="help_case_replied",
        summary=f"Support replied to help case: {case.subject}",
    )
    await db.flush()
    return message


async def _customer_reply_case(
    db: AsyncSession,
    *,
    current_user: User,
    case: HelpCase,
    body: str,
) -> HelpCaseMessage:
    now = datetime.now(timezone.utc)
    message = HelpCaseMessage(
        case_id=case.id,
        tenant_id=case.tenant_id,
        created_by_user_id=current_user.id,
        role="requester",
        body=body.strip(),
        internal_only=False,
    )
    case.last_message_at = now
    if case.status in {"resolved", "closed", "waiting_on_customer", "new"}:
        case.status = "triaging"
    db.add(message)
    _record_audit(
        db,
        tenant_id=case.tenant_id,
        user_id=current_user.id,
        entity_id=case.id,
        event_type="help_case_customer_reply",
        summary=f"Customer replied to help case: {case.subject}",
    )
    await db.flush()
    return message


@router.get("/articles", response_model=HelpArticleListResponse)
async def get_help_articles(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpArticleListResponse:
    articles = await list_help_articles(db, published_only=True)
    items = [HelpArticleResponse.model_validate(serialize_help_article(article)) for article in articles]
    return HelpArticleListResponse(items=items, total=len(items))


@router.get("/articles/{slug}", response_model=HelpArticleResponse)
async def get_help_article(
    slug: Annotated[str, Path(min_length=1, max_length=160)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpArticleResponse:
    article = await get_help_article_by_slug(db, slug=slug, published_only=True)
    if article is None:
        raise HTTPException(status_code=404, detail="Help article not found")
    return HelpArticleResponse.model_validate(serialize_help_article(article))


@router.get("/search", response_model=HelpSearchResponse)
async def search_help(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_path: Annotated[str | None, Query(max_length=500)] = None,
) -> HelpSearchResponse:
    matches = await search_help_articles(db, query=q, current_path=current_path, published_only=True)
    items = [HelpSearchResultResponse.model_validate(serialize_help_match(match)) for match in matches]
    return HelpSearchResponse(items=items, total=len(items))


@router.post("/assistant/query", response_model=HelpAssistantResponse)
async def query_help_assistant(
    body: Annotated[HelpAssistantRequest, Body(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpAssistantResponse:
    thread_uuid = _parse_optional_thread_id(body.thread_id) or uuid.uuid4()
    context = await build_help_context(
        db,
        current_user=current_user,
        current_path=body.current_path,
        account_id=body.account_id,
        action_id=body.action_id,
        finding_id=body.finding_id,
    )
    matches = await search_help_articles(
        db,
        query=body.question,
        current_path=body.current_path,
        published_only=True,
    )
    history = await list_thread_history(db, current_user=current_user, thread_id=thread_uuid)
    live_lookup_state, live_lookup_account = await resolve_live_lookup_state(
        db,
        current_user=current_user,
        question=body.question,
        context=context,
        confirm_live_lookup=body.confirm_live_lookup,
    )
    if live_lookup_state.status == "account_selection_required":
        answer_run = build_system_answer(
            answer=live_lookup_state.message or "Select an account before I run a live IAM security check.",
            matches=matches,
            confidence="medium",
            live_lookup=live_lookup_state,
        )
    elif live_lookup_state.status == "pending_confirmation":
        references = await build_ingested_security_references(
            db,
            tenant_id=current_user.tenant_id,
            account_id=live_lookup_state.account_id,
        )
        context["live_lookup"] = live_lookup_state.serialize()
        context["security_references"] = references
        answer_run = build_system_answer(
            answer=live_lookup_state.message or "Confirm if you want me to run a live read-only IAM check.",
            matches=matches,
            confidence="medium",
            live_lookup=live_lookup_state,
        )
    else:
        if live_lookup_state.status == "ready" and live_lookup_account is not None:
            executed_lookup = await run_live_iam_lookup(account=live_lookup_account, current_user=current_user)
            context["live_iam_snapshot"] = executed_lookup.serialize()
            live_lookup_state = executed_lookup
        elif live_lookup_state.status in {"disabled", "failed"}:
            context["live_lookup"] = live_lookup_state.serialize()
        answer_run = await generate_help_assistant_answer(
            question=body.question,
            context=context,
            matches=matches,
            history=history,
        )
        answer_run.live_lookup = live_lookup_state.serialize()
        answer_run.response_payload = {
            "provider_payload": answer_run.response_payload,
            "live_lookup": answer_run.live_lookup,
        }
    answer = answer_run.result
    interaction = HelpAssistantInteraction(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        thread_id=thread_uuid,
        question=body.question.strip(),
        current_path=body.current_path,
        request_context=context,
        cited_article_slugs=[item.slug for item in answer.citations],
        citations=[asdict(item) for item in answer.citations],
        referenced_entities=list(context.get("referenced_entities") or []),
        response_text=answer.answer,
        confidence=answer.confidence,
        suggested_case=answer.suggested_case,
        follow_up_questions=answer.follow_up_questions,
        context_gaps=answer.context_gaps,
        provider_name=answer_run.provider_name,
        model_name=answer_run.model_name,
        reasoning_effort=answer_run.reasoning_effort,
        usage=asdict(answer_run.usage),
        response_payload=answer_run.response_payload,
        latency_ms=answer_run.latency_ms,
        error_code=answer_run.error_code,
    )
    db.add(interaction)
    escalated_case_id = None
    if body.request_human:
        assistant_case_message = _assistant_case_message(
            history=history,
            answer_text=answer.answer,
            citations=[asdict(item) for item in answer.citations],
            context_gaps=answer.context_gaps,
        )
        case = await _create_case(
            db,
            current_user=current_user,
            subject=_help_subject(body.question),
            category="other",
            priority="normal",
            source="ai_escalation",
            body=body.question,
            current_path=body.current_path,
            referenced_entities=list(context.get("referenced_entities") or []),
            include_assistant_message=assistant_case_message,
        )
        interaction.escalated_case_id = case.id
        escalated_case_id = str(case.id)
        await create_help_case_notification(
            db,
            recipient=current_user,
            case=case,
            event="created",
            message="Your AI escalation was converted into a support case.",
        )
        send_help_case_admin_email(
            case=case,
            subject="New help case from AI escalation",
            summary=f"{current_user.email} escalated a help request from {body.current_path or 'the app'}.",
        )
    await db.commit()
    await db.refresh(interaction)
    response = _assistant_response(interaction)
    response.escalated_case_id = escalated_case_id
    response.live_lookup = answer_run.live_lookup
    return response


@router.post("/assistant/{interaction_id}/feedback", response_model=HelpAssistantResponse)
async def update_help_assistant_feedback(
    interaction_id: Annotated[str, Path(min_length=1, max_length=64)],
    body: Annotated[HelpAssistantFeedbackRequest, Body(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpAssistantResponse:
    try:
        interaction_uuid = uuid.UUID(interaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="interaction_id must be a valid UUID") from exc
    result = await db.execute(
        select(HelpAssistantInteraction).where(
            HelpAssistantInteraction.id == interaction_uuid,
            HelpAssistantInteraction.user_id == current_user.id,
            HelpAssistantInteraction.tenant_id == current_user.tenant_id,
        )
    )
    interaction = result.scalar_one_or_none()
    if interaction is None:
        raise HTTPException(status_code=404, detail="Help assistant interaction not found")
    interaction.helpful = body.helpful
    interaction.feedback_text = body.feedback_text.strip() if body.feedback_text else None
    await db.commit()
    return _assistant_response(interaction)


@router.post("/assistant/{interaction_id}/approve-case", response_model=HelpAssistantResponse)
async def approve_help_assistant_case(
    interaction_id: Annotated[str, Path(min_length=1, max_length=64)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpAssistantResponse:
    try:
        interaction_uuid = uuid.UUID(interaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="interaction_id must be a valid UUID") from exc
    result = await db.execute(
        select(HelpAssistantInteraction).where(
            HelpAssistantInteraction.id == interaction_uuid,
            HelpAssistantInteraction.user_id == current_user.id,
            HelpAssistantInteraction.tenant_id == current_user.tenant_id,
        )
    )
    interaction = result.scalar_one_or_none()
    if interaction is None:
        raise HTTPException(status_code=404, detail="Help assistant interaction not found")
    if interaction.escalated_case_id is None:
        history = await list_thread_history(db, current_user=current_user, thread_id=interaction.thread_id)
        assistant_case_message = _assistant_case_message(
            history=history[:-1],
            answer_text=interaction.response_text,
            citations=list(interaction.citations or []),
            context_gaps=list(interaction.context_gaps or []),
        )
        case = await _create_case(
            db,
            current_user=current_user,
            subject=_help_subject(interaction.question),
            category="other",
            priority="normal",
            source="ai_escalation",
            body=interaction.question,
            current_path=interaction.current_path,
            referenced_entities=list(interaction.referenced_entities or []),
            include_assistant_message=assistant_case_message,
        )
        interaction.escalated_case_id = case.id
        await create_help_case_notification(
            db,
            recipient=current_user,
            case=case,
            event="created",
            message="Your AI escalation was converted into a support case.",
        )
        send_help_case_admin_email(
            case=case,
            subject="New help case from AI escalation",
            summary=f"{current_user.email} escalated a help request from {interaction.current_path or 'the app'}.",
        )
        await db.commit()
        await db.refresh(interaction)
    return _assistant_response(interaction)


@router.get("/assistant/threads/{thread_id}", response_model=HelpAssistantThreadResponse)
async def get_help_assistant_thread(
    thread_id: Annotated[str, Path(min_length=1, max_length=64)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpAssistantThreadResponse:
    thread_uuid = _parse_optional_thread_id(thread_id)
    assert thread_uuid is not None
    thread = await get_help_thread(db, current_user=current_user, thread_id=thread_uuid)
    if thread is None:
        raise HTTPException(status_code=404, detail="Help assistant thread not found")
    return HelpAssistantThreadResponse.model_validate(serialize_help_thread(thread))


@router.get("/cases", response_model=HelpCaseListResponse)
async def get_my_help_cases(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpCaseListResponse:
    cases = await list_customer_cases(db, current_user=current_user)
    items = [_serialize_case_payload(case, include_internal=False) for case in cases]
    return HelpCaseListResponse(items=items, total=len(items))


@router.post("/cases", response_model=HelpCaseResponse, status_code=status.HTTP_201_CREATED)
async def create_help_case(
    body: Annotated[HelpCaseCreateRequest, Body(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpCaseResponse:
    context = await build_help_context(
        db,
        current_user=current_user,
        current_path=body.current_path,
        account_id=body.account_id,
        action_id=body.action_id,
        finding_id=body.finding_id,
    )
    case = await _create_case(
        db,
        current_user=current_user,
        subject=body.subject.strip(),
        category=body.category,
        priority=body.priority,
        source=body.source,
        body=body.body,
        current_path=body.current_path,
        referenced_entities=list(context.get("referenced_entities") or []),
    )
    await create_help_case_notification(
        db,
        recipient=current_user,
        case=case,
        event="created",
        message="Your support case has been created.",
    )
    send_help_case_admin_email(
        case=case,
        subject="New help case created",
        summary=f"{current_user.email} created a help case from {body.current_path or 'the app'}.",
    )
    await db.commit()
    case = await get_customer_case_or_404(db, case_id=str(case.id), current_user=current_user)
    return _serialize_case_payload(case, include_internal=False)


@router.get("/cases/{case_id}", response_model=HelpCaseResponse)
async def get_help_case(
    case_id: Annotated[str, Path(min_length=1, max_length=64)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpCaseResponse:
    case = await get_customer_case_or_404(db, case_id=case_id, current_user=current_user)
    return _serialize_case_payload(case, include_internal=False)


@router.post("/cases/{case_id}/messages", response_model=HelpCaseResponse)
async def reply_to_help_case(
    case_id: Annotated[str, Path(min_length=1, max_length=64)],
    body: Annotated[HelpCaseMessageCreateRequest, Body(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpCaseResponse:
    case = await get_customer_case_or_404(db, case_id=case_id, current_user=current_user)
    await _customer_reply_case(db, current_user=current_user, case=case, body=body.body)
    send_help_case_admin_email(
        case=case,
        subject="Customer replied to help case",
        summary=f"{current_user.email} replied to help case {case.subject}.",
    )
    await db.commit()
    case = await get_customer_case_or_404(db, case_id=case_id, current_user=current_user)
    return _serialize_case_payload(case, include_internal=False)


@router.post("/cases/{case_id}/attachments/upload", response_model=HelpAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_help_case_attachment(
    case_id: Annotated[str, Path(min_length=1, max_length=64)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    message_id: str = Form(...),
    file: UploadFile = File(...),
) -> HelpAttachmentResponse:
    case = await get_customer_case_or_404(db, case_id=case_id, current_user=current_user)
    try:
        message_uuid = uuid.UUID(message_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="message_id must be a valid UUID") from exc
    message = next((item for item in case.messages if item.id == message_uuid and not item.internal_only), None)
    if message is None:
        raise HTTPException(status_code=404, detail="Help case message not found")
    attachment = upload_case_attachment(
        case_id=case.id,
        message_id=message.id,
        tenant_id=case.tenant_id,
        file=file,
        internal_only=False,
        uploaded_by_user_id=current_user.id,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return HelpAttachmentResponse.model_validate(serialize_help_case_attachment(attachment))


@router.get("/cases/{case_id}/attachments/{attachment_id}/download", response_model=HelpAttachmentDownloadResponse)
async def download_help_case_attachment(
    case_id: Annotated[str, Path(min_length=1, max_length=64)],
    attachment_id: Annotated[str, Path(min_length=1, max_length=64)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpAttachmentDownloadResponse:
    case = await get_customer_case_or_404(db, case_id=case_id, current_user=current_user)
    try:
        attachment_uuid = uuid.UUID(attachment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="attachment_id must be a valid UUID") from exc
    attachment = next((item for item in case.attachments if item.id == attachment_uuid and not item.internal_only), None)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Help case attachment not found")
    return HelpAttachmentDownloadResponse(download_url=build_case_attachment_download_url(attachment))


@saas_router.get("/cases", response_model=HelpCaseListResponse)
async def get_admin_help_cases(
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[str | None, Query(max_length=32)] = None,
    priority: Annotated[str | None, Query(max_length=32)] = None,
    tenant_id: Annotated[str | None, Query(max_length=64)] = None,
    assigned_saas_admin_user_id: Annotated[str | None, Query(max_length=64)] = None,
    sla_state: Annotated[str | None, Query(max_length=32)] = None,
) -> HelpCaseListResponse:
    del admin
    cases = await list_admin_cases(
        db,
        status=status,
        priority=priority,
        tenant_id=tenant_id,
        assigned_saas_admin_user_id=assigned_saas_admin_user_id,
    )
    if sla_state:
        cases = [case for case in cases if compute_help_case_sla_state(case) == sla_state]
    items = [_serialize_case_payload(case, include_internal=True) for case in cases]
    return HelpCaseListResponse(items=items, total=len(items))


@saas_router.get("/cases/{case_id}", response_model=HelpCaseResponse)
async def get_admin_help_case(
    case_id: Annotated[str, Path(min_length=1, max_length=64)],
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpCaseResponse:
    del admin
    case = await get_admin_case_or_404(db, case_id=case_id)
    return _serialize_case_payload(case, include_internal=True)


@saas_router.patch("/cases/{case_id}", response_model=HelpCaseResponse)
async def update_admin_help_case(
    case_id: Annotated[str, Path(min_length=1, max_length=64)],
    body: Annotated[HelpCaseUpdateRequest, Body(...)],
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpCaseResponse:
    case = await get_admin_case_or_404(db, case_id=case_id)
    if body.status is not None:
        case.status = validate_case_status(body.status)
        if case.status == "resolved":
            case.resolved_at = datetime.now(timezone.utc)
        if case.status == "closed":
            case.closed_at = datetime.now(timezone.utc)
    if body.priority is not None:
        case.priority = validate_case_priority(body.priority)
    await _maybe_assign_admin(db, case=case, assigned_saas_admin_user_id=body.assigned_saas_admin_user_id)
    _record_audit(
        db,
        tenant_id=case.tenant_id,
        user_id=admin.id,
        entity_id=case.id,
        event_type="help_case_updated",
        summary=f"Support updated help case: {case.subject}",
    )
    requester = await db.get(User, case.requester_user_id)
    if requester is not None:
        await create_help_case_notification(
            db,
            recipient=requester,
            case=case,
            event="status_changed",
            message=f"Your support case is now {case.status}.",
        )
    await db.commit()
    case = await get_admin_case_or_404(db, case_id=case_id)
    return _serialize_case_payload(case, include_internal=True)


@saas_router.post("/cases/{case_id}/messages", response_model=HelpCaseResponse)
async def reply_to_admin_help_case(
    case_id: Annotated[str, Path(min_length=1, max_length=64)],
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[HelpCaseMessageCreateRequest, Body(...)],
    internal_only: Annotated[bool, Query()] = False,
) -> HelpCaseResponse:
    case = await get_admin_case_or_404(db, case_id=case_id)
    await _admin_reply_case(db, admin=admin, case=case, body=body.body, internal_only=internal_only)
    requester = await db.get(User, case.requester_user_id)
    if requester is not None and not internal_only:
        await create_help_case_notification(
            db,
            recipient=requester,
            case=case,
            event="reply",
            message="Support replied to your case.",
        )
        send_help_case_requester_email(
            requester_email=requester.email,
            case=case,
            subject="Support replied to your help case",
            summary="A support response is available for your case.",
        )
    await db.commit()
    case = await get_admin_case_or_404(db, case_id=case_id)
    return _serialize_case_payload(case, include_internal=True)


@saas_router.post("/cases/{case_id}/attachments/upload", response_model=HelpAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_admin_help_case_attachment(
    case_id: Annotated[str, Path(min_length=1, max_length=64)],
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    message_id: str = Form(...),
    internal_only: bool = Form(default=False),
    file: UploadFile = File(...),
) -> HelpAttachmentResponse:
    case = await get_admin_case_or_404(db, case_id=case_id)
    try:
        message_uuid = uuid.UUID(message_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="message_id must be a valid UUID") from exc
    message = next((item for item in case.messages if item.id == message_uuid), None)
    if message is None:
        raise HTTPException(status_code=404, detail="Help case message not found")
    attachment = upload_case_attachment(
        case_id=case.id,
        message_id=message.id,
        tenant_id=case.tenant_id,
        file=file,
        internal_only=internal_only,
        uploaded_by_user_id=admin.id,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return HelpAttachmentResponse.model_validate(serialize_help_case_attachment(attachment))


@saas_router.get("/cases/{case_id}/attachments/{attachment_id}/download", response_model=HelpAttachmentDownloadResponse)
async def download_admin_help_case_attachment(
    case_id: Annotated[str, Path(min_length=1, max_length=64)],
    attachment_id: Annotated[str, Path(min_length=1, max_length=64)],
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HelpAttachmentDownloadResponse:
    del admin
    case = await get_admin_case_or_404(db, case_id=case_id)
    try:
        attachment_uuid = uuid.UUID(attachment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="attachment_id must be a valid UUID") from exc
    attachment = next((item for item in case.attachments if item.id == attachment_uuid), None)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Help case attachment not found")
    return HelpAttachmentDownloadResponse(download_url=build_case_attachment_download_url(attachment))


@saas_router.get("/summary", response_model=dict[str, int])
async def get_admin_help_summary(
    admin: Annotated[User, Depends(require_saas_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, int]:
    del admin
    return {"total_cases": await count_admin_cases(db)}
