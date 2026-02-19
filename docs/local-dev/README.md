# Local Development Guide

This guide helps you set up and run AWS Security Autopilot locally for development and testing.

## Overview

The AWS Security Autopilot project consists of:

- **Backend API** — FastAPI application (`backend/main.py`) running on port 8000
- **Worker** — Python SQS consumer (`worker/main.py`) for background job processing
- **Database** — PostgreSQL (can use local Postgres or cloud-hosted like Neon)
- **SQS Queues** — Amazon SQS queues (can use real AWS queues or mocked for testing)

## Quick Start

1. **Set up environment** — See [Environment Setup](environment.md)
2. **Run backend** — See [Backend Development](backend.md)
3. **Run worker** — See [Worker Development](worker.md)
4. **Run tests** — See [Testing](tests.md)

---

## Prerequisites

- **Python 3.10+** (tested with 3.10 and 3.12)
- **PostgreSQL** — Local installation or cloud-hosted (e.g., Neon)
- **AWS Account** — For SQS queues (or use mocked queues for testing)
- **AWS CLI** — Configured with credentials (for SQS access)
- **Git** — For cloning the repository

---

## Directory Structure

```
.
├── backend/              # FastAPI application
│   ├── main.py          # API entrypoint
│   ├── config.py        # Configuration (Pydantic settings)
│   ├── routers/         # API route handlers
│   ├── services/        # Business logic
│   ├── models/          # SQLAlchemy models
│   └── utils/           # Utilities
├── worker/              # SQS worker
│   ├── main.py          # Worker entrypoint
│   ├── jobs/            # Job handlers
│   └── services/       # Worker services
├── alembic/             # Database migrations
├── tests/               # Test suite
├── .env                 # Environment variables (create from .env.example)
└── requirements.txt     # Python dependencies
```

---

## Next Steps

- **[Environment Setup](environment.md)** — Configure `.env` file and Python dependencies
- **[Backend Development](backend.md)** — Run the FastAPI API locally
- **[Worker Development](worker.md)** — Run the SQS worker locally
- **[Testing](tests.md)** — Run tests and understand test structure
- **[Frontend Development](frontend.md)** — Frontend setup (if applicable)

---

## Common Tasks

### Apply Database Migrations

```bash
# From project root
alembic upgrade head
```

### Check API Health

```bash
# Health check (always returns 200)
curl http://localhost:8000/health

# Readiness check (checks DB + SQS)
curl http://localhost:8000/ready
```

### View API Documentation

Once the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Check Worker Status

The worker logs to stdout. Look for:
- Queue connection status
- Job processing logs
- Error messages

---

## Troubleshooting

### Database Connection Issues

- Verify `DATABASE_URL` in `.env` is correct
- Ensure PostgreSQL is running (if using local DB)
- Check SSL settings for cloud-hosted databases (Neon requires SSL)

### SQS Queue Issues

- Verify AWS credentials are configured (`aws configure`)
- Check queue URLs in `.env` match your AWS account
- Ensure IAM permissions allow SQS access

### Migration Errors

- Ensure `DATABASE_URL_SYNC` is set (for Alembic)
- Check database revision: `alembic current`
- Apply migrations: `alembic upgrade head`

### Port Already in Use

- Change `uvicorn` port: `uvicorn backend.main:app --port 8001`
- Update `CORS_ORIGINS` in `.env` if frontend uses different port

---

## Development Workflow

1. **Create feature branch**
2. **Update `.env`** if new environment variables are needed
3. **Run migrations** if schema changes: `alembic upgrade head`
4. **Start backend**: `uvicorn backend.main:app --reload`
5. **Start worker** (in separate terminal): `python -m worker.main`
6. **Write tests** in `tests/`
7. **Run tests**: `pytest`
8. **Commit changes**

---

## See Also

- [API Reference](../api/README.md) — Complete API documentation
- [Data Model](../data-model/README.md) — Database schema
- [Owner Deployment Guide](../deployment/README.md) — Production deployment
