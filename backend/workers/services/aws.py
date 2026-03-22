"""
Reuse backend STS assume_role. Worker uses this for customer AWS access.
"""
from __future__ import annotations

from backend.services.aws import (
    WORKER_ASSUME_ROLE_SOURCE_IDENTITY,
    assume_role,
    build_assume_role_tags,
)

__all__ = [
    "WORKER_ASSUME_ROLE_SOURCE_IDENTITY",
    "assume_role",
    "build_assume_role_tags",
]
