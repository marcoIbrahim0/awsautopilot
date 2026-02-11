"""
Meta endpoints for lightweight frontend configuration.

These are intentionally non-sensitive flags that help the UI reflect backend behavior.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.config import settings
from backend.services.control_scope import IN_SCOPE_CONTROLS

router = APIRouter(prefix="/meta", tags=["meta"])


class ScopeMetaResponse(BaseModel):
    only_in_scope_controls: bool = Field(..., description="True when backend filters to in-scope controls only.")
    in_scope_controls_count: int = Field(..., description="Number of primary controls considered in-scope.")
    disabled_sources: list[str] = Field(
        default_factory=list,
        description="Finding sources disabled when only_in_scope_controls is true.",
    )


@router.get("/scope", response_model=ScopeMetaResponse)
async def get_scope_meta() -> ScopeMetaResponse:
    disabled_sources = ["access_analyzer", "inspector"] if settings.ONLY_IN_SCOPE_CONTROLS else []
    return ScopeMetaResponse(
        only_in_scope_controls=bool(settings.ONLY_IN_SCOPE_CONTROLS),
        in_scope_controls_count=len(IN_SCOPE_CONTROLS),
        disabled_sources=disabled_sources,
    )

