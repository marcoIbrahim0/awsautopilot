from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.help_content.catalog import HELP_ARTICLE_SEEDS, HelpArticleSeed
from backend.models.help_article import HelpArticle

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(slots=True)
class HelpArticleMatch:
    article: HelpArticle
    score: int
    snippet: str


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall((value or "").lower())


def _body_snippet(body: str, query_tokens: list[str]) -> str:
    compact = " ".join((body or "").split())
    if not compact:
        return ""
    if not query_tokens:
        return compact[:220]
    lowered = compact.lower()
    positions = [lowered.find(token) for token in query_tokens if lowered.find(token) >= 0]
    if not positions:
        return compact[:220]
    start = max(min(positions) - 60, 0)
    return compact[start : start + 220].strip()


def _score_article(article: HelpArticle, query: str, current_path: str | None) -> HelpArticleMatch:
    query_tokens = _tokens(query)
    title_tokens = _tokens(article.title)
    summary_tokens = _tokens(article.summary)
    body_tokens = _tokens(article.body)
    tags = [str(tag).lower() for tag in (article.tags or [])]
    routes = [str(route) for route in (article.related_routes or [])]
    score = 0
    for token in query_tokens:
        if token in title_tokens:
            score += 8
        if token in tags:
            score += 6
        if token in summary_tokens:
            score += 4
        if token in body_tokens:
            score += 2
    if current_path and any(current_path.startswith(route) for route in routes):
        score += 3
    if query.strip().lower() in article.title.lower():
        score += 10
    return HelpArticleMatch(article=article, score=score, snippet=_body_snippet(article.body, query_tokens))


def serialize_help_article(article: HelpArticle) -> dict[str, object]:
    return {
        "id": str(article.id),
        "slug": article.slug,
        "title": article.title,
        "summary": article.summary,
        "body": article.body,
        "audience": article.audience,
        "published": bool(article.published),
        "sort_order": int(article.sort_order or 0),
        "tags": list(article.tags or []),
        "related_routes": list(article.related_routes or []),
        "created_at": article.created_at.isoformat() if article.created_at else "",
        "updated_at": article.updated_at.isoformat() if article.updated_at else None,
    }


def serialize_help_match(match: HelpArticleMatch) -> dict[str, object]:
    payload = serialize_help_article(match.article)
    payload["score"] = match.score
    payload["snippet"] = match.snippet or match.article.summary
    return payload


def _article_changed(article: HelpArticle, seed: HelpArticleSeed) -> bool:
    return any(
        [
            article.title != seed["title"],
            article.summary != seed["summary"],
            article.body != seed["body"],
            article.audience != seed["audience"],
            bool(article.published) != bool(seed["published"]),
            int(article.sort_order or 0) != int(seed["sort_order"]),
            list(article.tags or []) != list(seed["tags"]),
            list(article.related_routes or []) != list(seed["related_routes"]),
        ]
    )


async def ensure_help_articles_synced(db: AsyncSession) -> None:
    seeds_by_slug = {seed["slug"]: seed for seed in HELP_ARTICLE_SEEDS}
    result = await db.execute(select(HelpArticle))
    existing = {article.slug: article for article in result.scalars().all()}
    changed = False
    for slug, seed in seeds_by_slug.items():
        article = existing.get(slug)
        if article is None:
            db.add(HelpArticle(**seed))
            changed = True
            continue
        if not _article_changed(article, seed):
            continue
        article.title = seed["title"]
        article.summary = seed["summary"]
        article.body = seed["body"]
        article.audience = seed["audience"]
        article.published = seed["published"]
        article.sort_order = seed["sort_order"]
        article.tags = seed["tags"]
        article.related_routes = seed["related_routes"]
        changed = True
    stale_slugs = set(existing) - set(seeds_by_slug)
    for slug in stale_slugs:
        await db.delete(existing[slug])
        changed = True
    if changed:
        await db.flush()


async def list_help_articles(
    db: AsyncSession,
    *,
    published_only: bool,
) -> list[HelpArticle]:
    query = select(HelpArticle).order_by(HelpArticle.sort_order.asc(), HelpArticle.title.asc())
    if published_only:
        query = query.where(HelpArticle.published.is_(True))
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_help_article_by_slug(
    db: AsyncSession,
    *,
    slug: str,
    published_only: bool,
) -> HelpArticle | None:
    query = select(HelpArticle).where(HelpArticle.slug == slug)
    if published_only:
        query = query.where(HelpArticle.published.is_(True))
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def search_help_articles(
    db: AsyncSession,
    *,
    query: str,
    current_path: str | None,
    published_only: bool,
    limit: int = 8,
) -> list[HelpArticleMatch]:
    articles = await list_help_articles(db, published_only=published_only)
    scored = [_score_article(article, query, current_path) for article in articles]
    filtered = [item for item in scored if item.score > 0]
    filtered.sort(key=lambda item: (-item.score, item.article.sort_order, item.article.title))
    return filtered[:limit]
