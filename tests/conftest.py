"""
Pytest fixtures for API tests.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient. Override get_db in tests that need a mock DB."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_dependency_overrides() -> None:
    """Clear app dependency overrides after each test to avoid cross-test pollution."""
    yield
    app.dependency_overrides.clear()
