"""
Worker configuration with service-first env loading.
"""
from __future__ import annotations

from pathlib import Path

from backend.config import Settings

_WORKER_ENV_FILE = Path("/Users/marcomaher/AWS Security Autopilot/backend/workers/.env")
_BACKEND_ENV_FILE = Path("/Users/marcomaher/AWS Security Autopilot/backend/.env")

_env_file = (
    str(_WORKER_ENV_FILE),
    str(_BACKEND_ENV_FILE),
)

settings = Settings(_env_file=_env_file)

__all__ = ["settings"]
