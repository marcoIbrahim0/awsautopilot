# Testing

This guide covers running tests and understanding the test structure for AWS Security Autopilot.

## Overview

The test suite uses **pytest** with async support (`pytest-asyncio`). Tests are located in the `tests/` directory and cover:
- API endpoints (health, readiness, endpoints)
- Worker job processing
- Database models and migrations
- Infrastructure validation (CloudFormation, resilience, security)
- Integration tests for core workflows

## Running Tests

### Basic Test Execution

From the project root:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_health_readiness.py

# Run tests with verbose output
pytest -v

# Run tests with coverage
pytest --cov=backend --cov=worker

# Run tests matching a pattern
pytest -k "health"
```

### Test Configuration

Tests use pytest configuration (can be in `pytest.ini`, `setup.cfg`, or `pyproject.toml`). Key settings:

- **Async support**: `pytest-asyncio` for async test functions
- **Test discovery**: Finds `test_*.py` files in `tests/` directory
- **Coverage**: Optional coverage reporting via `pytest-cov`

### Environment Setup for Tests

Tests may require:
- **Database**: Test database (can use same as dev or separate)
- **AWS credentials**: For SQS/other AWS service tests (or mocked)
- **Environment variables**: Some tests read from `.env` or set test-specific values

---

## Test Structure

### Test Files

Key test files:

- `test_health_readiness.py` — Health and readiness endpoint tests
- `test_worker_polling.py` — Worker SQS polling tests
- `test_worker_main_contract_quarantine.py` — Contract violation quarantine tests
- `test_reconcile_inventory_global_orchestration_worker.py` — Inventory reconciliation tests
- `test_cloudformation_phase3_resilience.py` — Phase 3 resilience tests
- `test_security_phase3_hardening.py` — Phase 3 security hardening tests
- `test_saas_system_health_phase3.py` — System health tests
- `test_control_plane_readiness.py` — Control-plane readiness tests
- `test_sqs_utils.py` — SQS utility tests

### Test Categories

#### Unit Tests

Test individual functions/modules in isolation:

```python
# Example: tests/test_sqs_utils.py
def test_parse_queue_region():
    assert parse_queue_region("https://sqs.us-east-1.amazonaws.com/123/queue") == "us-east-1"
```

#### Integration Tests

Test interactions between components:

```python
# Example: tests/test_health_readiness.py
def test_build_readiness_report_ready_when_db_and_sqs_are_healthy():
    # Mocks DB and SQS, tests readiness endpoint
    ...
```

#### API Tests

Test FastAPI endpoints:

```python
# Example: tests/test_health_readiness.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
```

#### Infrastructure Tests

Test CloudFormation templates and AWS resources:

```python
# Example: tests/test_cloudformation_phase3_resilience.py
def test_edge_protection_stack():
    # Validates CloudFormation stack creation
    ...
```

---

## Key Test Patterns

### Mocking AWS Services

Tests use `unittest.mock` to mock AWS services:

```python
from unittest.mock import patch, MagicMock

def test_sqs_operation():
    with patch("boto3.client") as mock_client:
        mock_sqs = MagicMock()
        mock_client.return_value = mock_sqs
        # Test code that uses SQS
        ...
```

### Async Test Functions

Use `pytest.mark.asyncio` for async tests:

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await my_async_function()
    assert result is not None
```

### Database Tests

Tests that interact with the database:

- Use test database (separate from dev/prod)
- May use fixtures to set up/tear down data
- Use transactions that roll back after each test

Example:

```python
@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()

@pytest.mark.asyncio
async def test_create_user(db_session):
    user = User(email="test@example.com", tenant_id=tenant_id)
    db_session.add(user)
    await db_session.commit()
    assert user.id is not None
```

### FastAPI Test Client

Use `TestClient` for API endpoint tests:

```python
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_endpoint():
    response = client.get("/api/endpoint")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

---

## Test Coverage

### Coverage Reports

Generate coverage reports:

```bash
# Run with coverage
pytest --cov=backend --cov=worker --cov-report=html

# View HTML report
open htmlcov/index.html
```

### Coverage Goals

Aim for:
- **Critical paths**: 80%+ coverage (auth, core business logic)
- **Utilities**: 70%+ coverage
- **Infrastructure**: 60%+ coverage (CloudFormation tests)

---

## Interpreting Test Results

### Health & Readiness Tests

**`test_health_readiness.py`** validates:
- `/health` endpoint returns 200
- `/ready` endpoint checks DB and SQS
- Readiness report includes dependency status

**What it means**:
- If health tests fail → API not starting correctly
- If readiness tests fail → DB or SQS connectivity issues

### Worker Tests

**`test_worker_polling.py`** validates:
- Worker can poll SQS queues
- Job routing by `job_type`
- Error handling and retries

**What it means**:
- If worker tests fail → SQS configuration or job handler issues

### Contract Quarantine Tests

**`test_worker_main_contract_quarantine.py`** validates:
- Malformed JSON → quarantine
- Missing required fields → quarantine
- Unknown job type → quarantine
- Unsupported schema version → quarantine

**What it means**:
- If quarantine tests fail → Queue contract validation broken

### Infrastructure Tests

**Phase 3 tests** (`test_cloudformation_phase3_resilience.py`, `test_security_phase3_hardening.py`, `test_saas_system_health_phase3.py`) validate:
- CloudFormation stacks deploy successfully
- Resilience measures (edge protection, DR backups)
- Security hardening
- System health endpoints

**What it means**:
- If infrastructure tests fail → CloudFormation templates or deployment issues

---

## Writing New Tests

### Test File Structure

```python
# tests/test_my_feature.py
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

def test_my_function():
    """Test description."""
    result = my_function()
    assert result == expected

@pytest.mark.asyncio
async def test_my_async_function():
    """Test async function."""
    result = await my_async_function()
    assert result is not None
```

### Best Practices

1. **Test names**: Descriptive, indicate what is being tested
2. **Arrange-Act-Assert**: Structure tests clearly
3. **Isolation**: Each test should be independent
4. **Mocking**: Mock external dependencies (AWS, DB for unit tests)
5. **Fixtures**: Use fixtures for common setup/teardown

### Example: API Endpoint Test

```python
from fastapi.testclient import TestClient
from backend.main import app
from unittest.mock import patch

client = TestClient(app)

def test_create_resource():
    """Test POST /api/resource endpoint."""
    with patch("backend.services.my_service.create_resource") as mock_create:
        mock_create.return_value = {"id": "123"}
        
        response = client.post(
            "/api/resource",
            json={"name": "Test"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 201
        assert response.json()["id"] == "123"
```

### Example: Worker Job Test

```python
from unittest.mock import patch, MagicMock
from worker.jobs.my_job import handle_my_job

def test_handle_my_job():
    """Test my job handler."""
    job = {
        "schema_version": 2,
        "job_type": "my_job",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "created_at": "2024-01-01T00:00:00Z"
    }
    
    with patch("worker.services.my_service.process") as mock_process:
        handle_my_job(job)
        mock_process.assert_called_once_with(job["tenant_id"])
```

---

## Continuous Integration

Tests should run in CI/CD pipelines:

- **On PR**: Run all tests
- **On merge**: Run tests + coverage report
- **Before deploy**: Run infrastructure tests

Example GitHub Actions workflow:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r backend/requirements.txt -r worker/requirements.txt
      - run: pytest --cov=backend --cov=worker
```

---

## Troubleshooting

### Tests Failing Locally

1. **Check environment**: Ensure `.env` is configured
2. **Check database**: Test database is accessible
3. **Check AWS credentials**: For AWS service tests
4. **Check dependencies**: Install test dependencies (`pytest`, `pytest-asyncio`)

### Async Test Warnings

If you see `RuntimeWarning: coroutine ... was never awaited`:

- Ensure test function is marked with `@pytest.mark.asyncio`
- Use `await` for async calls

### Database Test Issues

- Use separate test database (not dev/prod)
- Ensure migrations are applied: `alembic upgrade head`
- Use transactions that roll back after each test

### Mock Not Working

- Verify import path matches actual import in code
- Use `patch` context manager or decorator correctly
- Check mock is called (use `assert_called_once()`)

---

## Next Steps

- **[Backend Development](backend.md)** — Run the API locally
- **[Worker Development](worker.md)** — Run the worker locally
- **[API Reference](../api/README.md)** — API documentation

---

## See Also

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
