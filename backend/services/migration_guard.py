from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RevisionStatus:
    expected_heads: tuple[str, ...]
    current_heads: tuple[str, ...]

    @property
    def at_head(self) -> bool:
        return set(self.expected_heads) == set(self.current_heads)


def _alembic_config() -> Config:
    project_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url_sync)
    return cfg


def get_revision_status() -> RevisionStatus:
    cfg = _alembic_config()
    script = ScriptDirectory.from_config(cfg)
    expected_heads = tuple(sorted(script.get_heads()))

    engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_heads = tuple(sorted(context.get_current_heads() or ()))
    finally:
        engine.dispose()

    return RevisionStatus(expected_heads=expected_heads, current_heads=current_heads)


def assert_database_revision_at_head(*, component: str) -> None:
    if not settings.DB_REVISION_GUARD_ENABLED:
        logger.info("DB revision guard disabled; skipping startup migration check for component=%s", component)
        return
    if settings.ENV.lower() == "test" or os.getenv("PYTEST_CURRENT_TEST"):
        logger.info("DB revision guard skipped for test context (component=%s).", component)
        return

    status = get_revision_status()
    if status.at_head:
        return

    expected = ", ".join(status.expected_heads) or "<none>"
    current = ", ".join(status.current_heads) or "<none>"
    message = (
        f"Refusing to start {component}: database revision is not at Alembic head. "
        f"current={current} expected_head={expected}. "
        "Run 'alembic upgrade head' before restarting API/workers."
    )
    logger.critical(message)
    raise RuntimeError(message)
