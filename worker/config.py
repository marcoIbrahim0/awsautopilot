"""
Worker configuration. Reuses backend settings (same .env, same env vars).
Run from project root with PYTHONPATH so backend is importable.
"""
from __future__ import annotations

from backend.config import settings

__all__ = ["settings"]
