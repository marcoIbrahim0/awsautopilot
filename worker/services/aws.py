"""
Reuse backend STS assume_role. Worker uses this for customer AWS access.
"""
from __future__ import annotations

from backend.services.aws import assume_role

__all__ = ["assume_role"]
