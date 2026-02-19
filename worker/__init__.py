"""Compatibility shim for legacy worker.* imports.

Canonical module path: backend.workers.*
"""
from __future__ import annotations

from importlib import import_module

_backend_workers = import_module("backend.workers")
__all__ = getattr(_backend_workers, "__all__", [])
__path__ = _backend_workers.__path__
__spec__ = _backend_workers.__spec__


def __getattr__(name: str):
    return getattr(_backend_workers, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_backend_workers)))
