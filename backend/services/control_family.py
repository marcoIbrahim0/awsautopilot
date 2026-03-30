from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field

from backend.services.canonicalization import canonicalize_control_id, normalize_control_id_token
from backend.services.control_scope import equivalent_control_ids_for_control


class ControlFamilyResponse(BaseModel):
    source_control_ids: list[str] = Field(default_factory=list)
    canonical_control_id: str | None = None
    related_control_ids: list[str] = Field(default_factory=list)
    is_mapped: bool = False


def _normalize_control_ids(values: Iterable[str | None]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_control_id_token(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return sorted(ordered)


def build_control_family(
    source_control_ids: Iterable[str | None],
    *,
    canonical_control_id: str | None = None,
) -> ControlFamilyResponse:
    normalized_sources = _normalize_control_ids(source_control_ids)
    canonical = normalize_control_id_token(canonical_control_id)
    if canonical is None and normalized_sources:
        canonical = canonicalize_control_id(normalized_sources[0])
    related = list(equivalent_control_ids_for_control(canonical)) if canonical else []
    if canonical and (not related or related[0] != canonical):
        related = list(dict.fromkeys([canonical, *related]))
    is_mapped = bool(canonical and any(source != canonical for source in normalized_sources))
    return ControlFamilyResponse(
        source_control_ids=normalized_sources,
        canonical_control_id=canonical,
        related_control_ids=related,
        is_mapped=is_mapped,
    )
