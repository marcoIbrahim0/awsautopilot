FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install Python deps (API + worker) first for better layer caching.
COPY backend/requirements.txt /app/requirements-backend.txt
COPY backend/workers/requirements.txt /app/requirements-worker.txt
RUN pip install --no-cache-dir -r /app/requirements-backend.txt -r /app/requirements-worker.txt

# App code + migrations.
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY backend /app/backend
COPY backend/workers /app/backend/workers
COPY infrastructure /app/infrastructure

EXPOSE 8000

# Default command (ECS can override per-service).
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

