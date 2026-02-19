# Backend Development

This guide covers running the FastAPI backend API locally for development.

## Overview

The backend API (`backend/main.py`) is a FastAPI application that provides REST endpoints for:
- Authentication and user management
- AWS account registration and validation
- Findings and actions management
- Remediation runs and approvals
- Evidence exports and baseline reports
- SaaS admin endpoints

## Running the Backend

### Basic Startup

From the project root:

```bash
# Activate virtual environment (if using one)
source venv/bin/activate

# Run with uvicorn (development mode with auto-reload)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **HTTP**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Startup Sequence

On startup, the backend:

1. **Loads configuration** from `.env` via `backend/config.py`
2. **Checks database revision** — Fails fast if DB revision != Alembic head (via `backend/services/migration_guard.py`)
3. **Mounts routers** — All API routes under `/api` prefix
4. **Starts uvicorn** — ASGI server

### Health Endpoints

- **`GET /health`** — Basic health check (always returns 200)
- **`GET /ready`** — Readiness check (checks DB connectivity and SQS queue accessibility)
- **`GET /health/ready`** — Alias for `/ready`

Example:

```bash
# Health check
curl http://localhost:8000/health

# Readiness check (returns 503 if DB or SQS unavailable)
curl http://localhost:8000/ready
```

---

## Database Migrations

The backend automatically checks database revision on startup. If migrations are not applied, the API will fail to start.

### Apply Migrations

```bash
# Check current revision
alembic current

# Apply all pending migrations
alembic upgrade head

# View migration history
alembic history
```

### Migration Guard

The backend uses a migration guard (`backend/services/migration_guard.py`) that:
- Checks database revision at startup
- Fails fast if revision != Alembic head
- Prevents running against outdated schema

To disable (not recommended):

```bash
DB_REVISION_GUARD_ENABLED=false
```

---

## Development Mode Features

### Auto-Reload

Use `--reload` flag for automatic restart on code changes:

```bash
uvicorn backend.main:app --reload
```

### Debug Logging

Set `LOG_LEVEL=DEBUG` in `.env` for verbose logging:

```bash
LOG_LEVEL=DEBUG
```

### CORS Configuration

Configure allowed origins in `.env`:

```bash
CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
```

The backend uses `CORSMiddleware` to allow requests from frontend origins.

---

## API Structure

### Router Organization

Routers are mounted under `/api` prefix:

- `/api/auth` — Authentication (signup, login, logout, `/me`)
- `/api/aws-accounts` — AWS account registration and management
- `/api/findings` — Security findings (Security Hub, Access Analyzer, Inspector)
- `/api/actions` — Prioritized actions derived from findings
- `/api/action-groups` — Action grouping and runs
- `/api/remediation-runs` — Remediation execution (direct fix + PR bundles)
- `/api/exceptions` — Exception/suppression management
- `/api/exports` — Evidence/compliance pack exports
- `/api/baseline-report` — 48h baseline report generation
- `/api/users` — User management, invites, digest/Slack settings
- `/api/reconciliation` — Inventory reconciliation
- `/api/control-plane` — Control-plane event ingestion
- `/api/internal` — Internal endpoints (weekly digest, reconciliation scheduler)
- `/api/saas` — SaaS admin endpoints (system health, tenant management)
- `/api/support-files` — Support file downloads
- `/api/meta` — Scope metadata

### Authentication

Most endpoints require authentication via JWT tokens:

- **Bearer token** — `Authorization: Bearer <token>`
- **HTTP-only cookie** — `Cookie: access_token=<token>` + `X-CSRF-Token` header

See [API Reference](../api/README.md) for authentication details.

---

## Testing the API

### Using curl

```bash
# Health check
curl http://localhost:8000/health

# Signup (no auth required)
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123","tenant_name":"Test Tenant"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# Get current user (requires auth)
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <token>"
```

### Using Swagger UI

Visit http://localhost:8000/docs for interactive API documentation:
- Try endpoints directly from the browser
- View request/response schemas
- Authenticate using the "Authorize" button

---

## Common Development Tasks

### Adding a New Endpoint

1. **Create router** (if new domain) or add to existing router:
   ```python
   # backend/routers/my_feature.py
   from fastapi import APIRouter
   router = APIRouter()
   
   @router.get("/my-endpoint")
   async def my_endpoint():
       return {"message": "Hello"}
   ```

2. **Mount router** in `backend/main.py`:
   ```python
   from backend.routers.my_feature import router as my_feature_router
   app.include_router(my_feature_router, prefix="/api")
   ```

3. **Add authentication** (if needed):
   ```python
   from backend.auth import get_current_user
   
   @router.get("/my-endpoint")
   async def my_endpoint(current_user=Depends(get_current_user)):
       return {"user": current_user.email}
   ```

### Adding a New Database Model

1. **Create model** in `backend/models/`:
   ```python
   from backend.models.base import Base
   from sqlalchemy import Column, String
   
   class MyModel(Base):
       __tablename__ = "my_table"
       id = Column(String, primary_key=True)
   ```

2. **Create migration**:
   ```bash
   alembic revision --autogenerate -m "add my_table"
   alembic upgrade head
   ```

3. **Import model** in `backend/models/__init__.py` (if needed for Alembic autogenerate)

### Adding Environment Variables

1. **Add to `backend/config.py`**:
   ```python
   class Settings(BaseSettings):
       MY_NEW_VAR: str = Field(default="default", description="My new variable")
   ```

2. **Update `.env`** with the new variable

3. **Use in code**:
   ```python
   from backend.config import settings
   value = settings.MY_NEW_VAR
   ```

---

## Debugging

### Logging

Set `LOG_LEVEL=DEBUG` in `.env` for verbose logs:

```bash
LOG_LEVEL=DEBUG
```

Logs include:
- Request/response details
- Database queries (when `LOG_LEVEL=DEBUG`)
- SQS operations
- Authentication events

### Database Queries

With `LOG_LEVEL=DEBUG`, SQLAlchemy logs all queries. To see raw SQL:

```python
# In code
import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
```

### Error Handling

FastAPI returns structured error responses:

```json
{
  "detail": "Error message"
}
```

Check backend logs for full stack traces.

---

## Performance Considerations

### Database Connection Pooling

SQLAlchemy uses connection pooling automatically. Configure pool size in `DATABASE_URL`:

```
postgresql+asyncpg://user:pass@host/db?pool_size=10&max_overflow=20
```

### Async Operations

The backend uses async/await for I/O operations:
- Database queries (async SQLAlchemy)
- SQS operations (boto3 async not used; consider `aioboto3` for async SQS)

### Caching

No built-in caching. Consider adding Redis for:
- JWT token validation
- Frequently accessed data

---

## Production Considerations

For production deployment, see [Owner Deployment Guide](../deployment/infrastructure-ecs.md). Key differences:

- **Secrets**: Use AWS Secrets Manager instead of `.env`
- **Database**: RDS PostgreSQL with automated backups
- **Deployment**: ECS Fargate or Lambda (not uvicorn directly)
- **Monitoring**: CloudWatch logs and metrics
- **SSL**: ALB/CloudFront with ACM certificates

---

## Next Steps

- **[Worker Development](worker.md)** — Run the SQS worker locally
- **[Testing](tests.md)** — Run tests
- **[API Reference](../api/README.md)** — Complete API documentation

---

## Troubleshooting

### Port Already in Use

```bash
# Use different port
uvicorn backend.main:app --port 8001

# Or kill process on port 8000
lsof -ti:8000 | xargs kill
```

### Database Connection Errors

- Verify `DATABASE_URL` is correct
- Check PostgreSQL is running (if local)
- Ensure SSL settings are correct (for cloud-hosted DBs)

### Migration Errors

- Check current revision: `alembic current`
- Apply migrations: `alembic upgrade head`
- Verify `DATABASE_URL_SYNC` is set (for Alembic)

### Import Errors

- Ensure you're running from project root
- Check `PYTHONPATH` includes project root
- Verify virtual environment is activated
