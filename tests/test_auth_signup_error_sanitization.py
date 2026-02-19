from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_signup_does_not_return_raw_exception_detail() -> None:
    auth_router = _read("backend/routers/auth.py")

    assert "detail=str(e)" not in auth_router
    assert "correlation_id = uuid.uuid4().hex" in auth_router
    assert "correlation_id={correlation_id}" in auth_router
