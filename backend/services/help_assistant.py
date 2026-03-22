from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.help_assistant_interaction import HelpAssistantInteraction
from backend.models.user import User
from backend.services.help_center import HelpArticleMatch
from backend.services.help_live_iam import HelpLiveLookupState

logger = logging.getLogger(__name__)

_OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
_MAX_HISTORY_TURNS = 4
_MAX_ARTICLES = 3
_MAX_ARTICLE_CHARS = 1200
_MAX_FOLLOW_UPS = 3
_MAX_CONTEXT_GAPS = 3
_MAX_ANSWER_CHARS = 420
_MAX_ANSWER_SENTENCES = 3
_SECRET_PATTERNS = (
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+"),
    re.compile(r"(?i)\bauthorization:\s*bearer\s+[A-Za-z0-9._-]+"),
)


@dataclass(slots=True)
class HelpAssistantCitation:
    slug: str
    title: str
    summary: str


@dataclass(slots=True)
class HelpAssistantUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class HelpAssistantStructuredResult:
    answer: str
    confidence: str
    suggested_case: bool
    citations: list[HelpAssistantCitation]
    follow_up_questions: list[str]
    context_gaps: list[str]


@dataclass(slots=True)
class HelpAssistantRunResult:
    result: HelpAssistantStructuredResult
    provider_name: str | None
    model_name: str | None
    reasoning_effort: str | None
    usage: HelpAssistantUsage
    response_payload: dict[str, object]
    latency_ms: int | None
    error_code: str | None
    live_lookup: dict[str, object] | None = None


@dataclass(slots=True)
class HelpAssistantTurn:
    interaction_id: str
    question: str
    answer: str
    confidence: str
    suggested_case: bool
    citations: list[HelpAssistantCitation]
    follow_up_questions: list[str]
    context_gaps: list[str]
    helpful: bool | None
    feedback_text: str | None
    created_at: str
    escalated_case_id: str | None
    live_lookup: dict[str, object] | None = None


@dataclass(slots=True)
class HelpAssistantThread:
    thread_id: str
    current_path: str | None
    turns: list[HelpAssistantTurn]


def _article_excerpt(body: str) -> str:
    compact = " ".join((body or "").split())
    return compact[:_MAX_ARTICLE_CHARS]


def _citation_pool(matches: list[HelpArticleMatch]) -> dict[str, HelpAssistantCitation]:
    pool: dict[str, HelpAssistantCitation] = {}
    for match in matches[:_MAX_ARTICLES]:
        pool[match.article.slug] = HelpAssistantCitation(
            slug=match.article.slug,
            title=match.article.title,
            summary=match.article.summary,
        )
    return pool


def _fallback_result(matches: list[HelpArticleMatch], reason: str) -> HelpAssistantRunResult:
    citations = list(_citation_pool(matches).values())
    answer = (
        "I can’t produce a grounded answer right now. "
        "If you want, I can help open a support case."
    )
    if citations:
        answer = f"{answer}\n\nRelevant Help Center articles are still attached below."
    result = HelpAssistantStructuredResult(
        answer=answer,
        confidence="low",
        suggested_case=True,
        citations=citations,
        follow_up_questions=[],
        context_gaps=[reason],
    )
    return HelpAssistantRunResult(
        result=result,
        provider_name="openai",
        model_name=settings.OPENAI_HELP_MODEL,
        reasoning_effort=settings.OPENAI_HELP_REASONING_EFFORT,
        usage=HelpAssistantUsage(),
        response_payload={"fallback_reason": reason},
        latency_ms=None,
        error_code=reason,
        live_lookup=None,
    )


def build_system_answer(
    *,
    answer: str,
    matches: list[HelpArticleMatch],
    confidence: str = "medium",
    suggested_case: bool = False,
    context_gaps: list[str] | None = None,
    live_lookup: HelpLiveLookupState | None = None,
) -> HelpAssistantRunResult:
    citations = list(_citation_pool(matches).values())
    result = HelpAssistantStructuredResult(
        answer=answer.strip(),
        confidence=confidence,
        suggested_case=suggested_case,
        citations=citations,
        follow_up_questions=[],
        context_gaps=context_gaps or [],
    )
    payload = {
        "system": True,
        "live_lookup": live_lookup.serialize() if live_lookup else None,
    }
    return HelpAssistantRunResult(
        result=result,
        provider_name="system",
        model_name=None,
        reasoning_effort=None,
        usage=HelpAssistantUsage(),
        response_payload=payload,
        latency_ms=None,
        error_code=None,
        live_lookup=payload["live_lookup"],
    )


def _sanitize_context(context: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {"current_path": context.get("current_path")}
    for key in (
        "account",
        "action",
        "finding",
        "tenant_settings",
        "referenced_entities",
        "platform_summary",
        "live_lookup",
        "live_iam_snapshot",
        "security_references",
        "resolved_account_id",
    ):
        value = context.get(key)
        if value:
            payload[key] = value
    return payload


def _history_messages(history: list[HelpAssistantInteraction]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for turn in history[-_MAX_HISTORY_TURNS:]:
        items.append({"role": "user", "content": turn.question})
        items.append({"role": "assistant", "content": turn.response_text})
    return items


def _article_packets(matches: list[HelpArticleMatch]) -> list[dict[str, object]]:
    packets: list[dict[str, object]] = []
    for match in matches[:_MAX_ARTICLES]:
        packets.append(
            {
                "slug": match.article.slug,
                "title": match.article.title,
                "summary": match.article.summary,
                "excerpt": _article_excerpt(match.article.body),
                "tags": list(match.article.tags or []),
                "related_routes": list(match.article.related_routes or []),
            }
        )
    return packets


def _developer_prompt() -> str:
    return "\n".join(
        [
            "You are the Help Hub assistant for AWS Security Autopilot.",
            "Respond naturally and briefly to greetings or vague questions. Ask for clarification if needed.",
            "Default to at most 2 short sentences or 3 short bullets unless the user explicitly asks for detail.",
            "Use only the provided help articles and platform-visible SaaS context to inform your answers.",
            "When discussing the customer's current posture or score, use only metrics present in platform_summary.",
            "Do not mention hidden totals, backend-only data, raw payloads, request context internals, or internal field names.",
            "When live IAM observations are provided, treat them as current read-only account state.",
            "Do not invent product state, hidden data, secrets, or unsupported features.",
            "If the user asks a specific technical question and the provided evidence is weak or incomplete, set suggested_case to true and OFFER to help them open a support case. Do not state that you have opened or created a case automatically.",
            "Citations must use only article slugs present in the supplied article packets.",
            "Keep answers product-specific, read-only, concise, and clearly separate platform data from live observations.",
        ]
    )


def _user_prompt(question: str, context: dict[str, object], matches: list[HelpArticleMatch]) -> str:
    payload = {
        "question": question.strip(),
        "context": _sanitize_context(context),
        "articles": _article_packets(matches),
    }
    return json.dumps(payload, ensure_ascii=True)


def _response_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "answer",
            "confidence",
            "suggested_case",
            "citations",
            "follow_up_questions",
            "context_gaps",
        ],
        "properties": {
            "answer": {"type": "string"},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "suggested_case": {"type": "boolean"},
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["slug"],
                    "properties": {"slug": {"type": "string"}},
                },
            },
            "follow_up_questions": {"type": "array", "items": {"type": "string"}},
            "context_gaps": {"type": "array", "items": {"type": "string"}},
        },
    }


def _supports_reasoning_effort(model_name: str) -> bool:
    normalized = (model_name or "").strip().lower()
    return normalized.startswith("gpt-5")


def _request_body(question: str, context: dict[str, object], matches: list[HelpArticleMatch], history: list[HelpAssistantInteraction]) -> dict[str, object]:
    payload = {
        "model": settings.OPENAI_HELP_MODEL,
        "input": [
            {"role": "developer", "content": _developer_prompt()},
            *_history_messages(history),
            {"role": "user", "content": _user_prompt(question, context, matches)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "help_assistant_response",
                "schema": _response_schema(),
                "strict": True,
            }
        },
    }
    if _supports_reasoning_effort(settings.OPENAI_HELP_MODEL):
        payload["reasoning"] = {"effort": settings.OPENAI_HELP_REASONING_EFFORT}
    return payload


def _content_text(content: dict[str, object]) -> str:
    if isinstance(content.get("text"), str):
        return str(content["text"])
    text_obj = content.get("text")
    if isinstance(text_obj, dict) and isinstance(text_obj.get("value"), str):
        return str(text_obj["value"])
    return ""


def _extract_response_text(payload: dict[str, object]) -> str:
    output = payload.get("output")
    if not isinstance(output, list):
        return ""
    chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            text = _content_text(content)
            if text:
                chunks.append(text)
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def _usage_from_payload(payload: dict[str, object]) -> HelpAssistantUsage:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return HelpAssistantUsage()
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    return HelpAssistantUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _normalized_strings(raw: object, *, limit: int) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        text = str(item).strip() if item is not None else ""
        if text and text not in values:
            values.append(text[:240])
        if len(values) >= limit:
            break
    return values


def _normalized_citations(raw: object, matches: list[HelpArticleMatch]) -> list[HelpAssistantCitation]:
    pool = _citation_pool(matches)
    citations: list[HelpAssistantCitation] = []
    if not isinstance(raw, list):
        return citations
    for item in raw:
        slug = str(item.get("slug")).strip() if isinstance(item, dict) and item.get("slug") else ""
        citation = pool.get(slug)
        if citation and citation.slug not in {entry.slug for entry in citations}:
            citations.append(citation)
    return citations


def _structured_result(payload: dict[str, object], matches: list[HelpArticleMatch]) -> HelpAssistantStructuredResult:
    text = _extract_response_text(payload)
    if not text:
        raise ValueError("missing_output_text")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("invalid_output_shape")
    citations = _normalized_citations(data.get("citations"), matches)
    confidence = str(data.get("confidence") or "low").lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "low"
    answer = str(data.get("answer") or "").strip()
    if not answer:
        raise ValueError("missing_answer")
    return HelpAssistantStructuredResult(
        answer=answer,
        confidence=confidence,
        suggested_case=bool(data.get("suggested_case")),
        citations=citations,
        follow_up_questions=_normalized_strings(data.get("follow_up_questions"), limit=_MAX_FOLLOW_UPS),
        context_gaps=_normalized_strings(data.get("context_gaps"), limit=_MAX_CONTEXT_GAPS),
    )


def _validated_result(payload: dict[str, object], matches: list[HelpArticleMatch]) -> HelpAssistantStructuredResult:
    result = _structured_result(payload, matches)
    if result.confidence == "low":
        result.suggested_case = True
    return _finalize_result(result)


def _contains_secret_like_content(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _SECRET_PATTERNS)


def _trim_answer(answer: str) -> str:
    compact = re.sub(r"\s+", " ", (answer or "").strip())
    if len(compact) <= _MAX_ANSWER_CHARS:
        return compact
    sentences = re.split(r"(?<=[.!?])\s+", compact)
    shortened = " ".join(sentences[:_MAX_ANSWER_SENTENCES]).strip()
    if shortened and len(shortened) <= _MAX_ANSWER_CHARS:
        return shortened
    return compact[: _MAX_ANSWER_CHARS - 3].rstrip() + "..."


def _blocked_secret_result(result: HelpAssistantStructuredResult) -> HelpAssistantStructuredResult:
    gaps = list(result.context_gaps)
    gaps.append("I can only share platform-visible information and cannot expose secrets or internal-only data.")
    return HelpAssistantStructuredResult(
        answer="I can only share platform-visible information. I can’t reveal secrets or internal-only data.",
        confidence="medium",
        suggested_case=True,
        citations=result.citations,
        follow_up_questions=[],
        context_gaps=gaps[:_MAX_CONTEXT_GAPS],
    )


def _finalize_result(result: HelpAssistantStructuredResult) -> HelpAssistantStructuredResult:
    if _contains_secret_like_content(result.answer):
        return _blocked_secret_result(result)
    result.answer = _trim_answer(result.answer)
    return result


async def _openai_payload(request_body: dict[str, object]) -> tuple[dict[str, object], int]:
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.OPENAI_HELP_TIMEOUT_SECONDS)
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(_OPENAI_RESPONSES_URL, headers=headers, json=request_body)
    latency_ms = int((time.perf_counter() - started) * 1000)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("invalid_provider_payload")
    return payload, latency_ms


async def generate_help_assistant_answer(
    *,
    question: str,
    context: dict[str, object],
    matches: list[HelpArticleMatch],
    history: list[HelpAssistantInteraction],
) -> HelpAssistantRunResult:
    if not settings.OPENAI_HELP_ENABLED or not settings.OPENAI_API_KEY:
        return _fallback_result(matches, "provider_unavailable")
    request_body = _request_body(question, context, matches, history)
    try:
        payload, latency_ms = await _openai_payload(request_body)
        result = _validated_result(payload, matches)
    except httpx.TimeoutException:
        logger.warning("help assistant provider timeout")
        return _fallback_result(matches, "provider_timeout")
    except httpx.HTTPStatusError as exc:
        logger.warning("help assistant provider http error status=%s", exc.response.status_code)
        return _fallback_result(matches, "provider_http_error")
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("help assistant provider parse error code=%s", exc)
        return _fallback_result(matches, str(exc))
    return HelpAssistantRunResult(
        result=result,
        provider_name="openai",
        model_name=str(payload.get("model") or settings.OPENAI_HELP_MODEL),
        reasoning_effort=settings.OPENAI_HELP_REASONING_EFFORT,
        usage=_usage_from_payload(payload),
        response_payload=payload,
        latency_ms=latency_ms,
        error_code=None,
        live_lookup=None,
    )


async def get_help_thread(
    db: AsyncSession,
    *,
    current_user: User,
    thread_id: uuid.UUID,
) -> HelpAssistantThread | None:
    result = await db.execute(
        select(HelpAssistantInteraction)
        .where(
            HelpAssistantInteraction.thread_id == thread_id,
            HelpAssistantInteraction.tenant_id == current_user.tenant_id,
            HelpAssistantInteraction.user_id == current_user.id,
        )
        .order_by(HelpAssistantInteraction.created_at.asc())
    )
    interactions = list(result.scalars().all())
    if not interactions:
        return None
    turns = [_serialize_turn(item) for item in interactions]
    return HelpAssistantThread(
        thread_id=str(thread_id),
        current_path=interactions[-1].current_path,
        turns=turns,
    )


async def list_thread_history(
    db: AsyncSession,
    *,
    current_user: User,
    thread_id: uuid.UUID | None,
) -> list[HelpAssistantInteraction]:
    if thread_id is None:
        return []
    result = await db.execute(
        select(HelpAssistantInteraction)
        .where(
            HelpAssistantInteraction.thread_id == thread_id,
            HelpAssistantInteraction.tenant_id == current_user.tenant_id,
            HelpAssistantInteraction.user_id == current_user.id,
        )
        .order_by(HelpAssistantInteraction.created_at.asc())
    )
    return list(result.scalars().all())


def _serialize_citations(raw: object, slugs: list[str]) -> list[HelpAssistantCitation]:
    citations: list[HelpAssistantCitation] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("slug") and item.get("title"):
                citations.append(
                    HelpAssistantCitation(
                        slug=str(item["slug"]),
                        title=str(item["title"]),
                        summary=str(item.get("summary") or ""),
                    )
                )
    if citations:
        return citations
    return [HelpAssistantCitation(slug=slug, title=slug.replace("-", " ").title(), summary="") for slug in slugs]


def _serialize_turn(interaction: HelpAssistantInteraction) -> HelpAssistantTurn:
    live_lookup = interaction.response_payload.get("live_lookup") if isinstance(interaction.response_payload, dict) else None
    return HelpAssistantTurn(
        interaction_id=str(interaction.id),
        question=interaction.question,
        answer=interaction.response_text,
        confidence=interaction.confidence,
        suggested_case=bool(interaction.suggested_case),
        citations=_serialize_citations(interaction.citations, interaction.cited_article_slugs),
        follow_up_questions=[str(item) for item in interaction.follow_up_questions or []],
        context_gaps=[str(item) for item in interaction.context_gaps or []],
        helpful=interaction.helpful,
        feedback_text=interaction.feedback_text,
        created_at=interaction.created_at.isoformat() if interaction.created_at else "",
        escalated_case_id=str(interaction.escalated_case_id) if interaction.escalated_case_id else None,
        live_lookup=live_lookup if isinstance(live_lookup, dict) else None,
    )


def serialize_help_thread(thread: HelpAssistantThread) -> dict[str, object]:
    return {
        "thread_id": thread.thread_id,
        "current_path": thread.current_path,
        "turns": [
            {
                "interaction_id": turn.interaction_id,
                "question": turn.question,
                "answer": turn.answer,
                "confidence": turn.confidence,
                "suggested_case": turn.suggested_case,
                "citations": [asdict(citation) for citation in turn.citations],
                "follow_up_questions": turn.follow_up_questions,
                "context_gaps": turn.context_gaps,
                "helpful": turn.helpful,
                "feedback_text": turn.feedback_text,
                "created_at": turn.created_at,
                "escalated_case_id": turn.escalated_case_id,
                "live_lookup": turn.live_lookup,
            }
            for turn in thread.turns
        ],
    }
