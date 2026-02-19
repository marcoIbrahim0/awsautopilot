#!/usr/bin/env python3
"""
Step 7 verification script.

Run from project root with the project venv (so pydantic_settings and deps are available):

  source venv/bin/activate
  PYTHONPATH=. python scripts/verify_step7.py

Or explicitly: PYTHONPATH=. ./venv/bin/python scripts/verify_step7.py

Checks:
- Migrations 0007 (remediation_runs) and 0008 (audit_log) are applied
- PR bundle scaffold returns expected shape
- Remediation audit guards work
- SQS remediation_run payload builder
- Worker handler registered for remediation_run
"""
from __future__ import annotations

import sys
import uuid


def _ensure_deps() -> None:
    """Fail fast if pydantic_settings is missing (venv not used)."""
    try:
        import pydantic_settings  # noqa: F401
    except ImportError:
        print(
            "Missing dependency: pydantic_settings. Run with the project venv:\n"
            "  source venv/bin/activate\n"
            "  PYTHONPATH=. python scripts/verify_step7.py\n"
            "Or: PYTHONPATH=. ./venv/bin/python scripts/verify_step7.py",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> int:
    _ensure_deps()
    errors: list[str] = []
    ok: list[str] = []

    # 1. PR bundle service (Step 9.1: load action, dispatch by action_type)
    try:
        from backend.services.pr_bundle import (
            ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS,
            generate_pr_bundle,
            PRBundleResult,
            TERRAFORM_FORMAT,
            CLOUDFORMATION_FORMAT,
        )

        def _make_action(action_type: str = "s3_block_public_access", **kwargs: object) -> object:
            defaults = {
                "id": uuid.uuid4(),
                "action_type": action_type,
                "account_id": "123456789012",
                "region": "eu-north-1",
                "target_id": "target-1",
                "title": "Remediation",
                "control_id": "control-1",
            }
            defaults.update(kwargs)
            return type("ActionLike", (), defaults)()

        action = _make_action(action_type=ACTION_TYPE_S3_BLOCK_PUBLIC_ACCESS)
        r = generate_pr_bundle(action, "terraform")
        assert isinstance(r, dict), "pr_bundle should return dict"
        assert "format" in r and r["format"] == "terraform", "format"
        assert "files" in r and len(r["files"]) >= 2, "files (Step 9.2: providers.tf + s3_block_public_access.tf)"
        assert "steps" in r and len(r["steps"]) >= 4, "steps"
        paths = [f.get("path") for f in r["files"]]
        assert "providers.tf" in paths, "providers.tf (Step 9.2)"
        assert "s3_block_public_access.tf" in paths, "s3_block_public_access.tf"
        resource_file = next(f for f in r["files"] if f["path"] == "s3_block_public_access.tf")
        assert "aws_s3_account_public_access_block" in resource_file["content"], "S3 Terraform content"
        r2 = generate_pr_bundle(action, "cloudformation")
        assert r2["format"] == "cloudformation", "cloudformation format"
        assert r2["files"][0]["path"].endswith(".yaml"), "cloudformation file"
        r3 = generate_pr_bundle(None, "terraform")
        assert r3["format"] == "terraform" and len(r3["files"]) >= 1, "None action returns guidance"
        ok.append("PR bundle service: format, files, steps, dispatch OK")
    except Exception as e:
        errors.append(f"PR bundle service: {e}")

    # 2. Remediation audit guards
    try:
        from backend.services.remediation_audit import is_run_completed, allow_update_outcome, COMPLETED_STATUSES
        from backend.models.enums import RemediationRunStatus
        assert is_run_completed(RemediationRunStatus.success) is True
        assert is_run_completed(RemediationRunStatus.failed) is True
        assert is_run_completed(RemediationRunStatus.pending) is False
        assert is_run_completed("success") is True
        assert is_run_completed("failed") is True
        # allow_update_outcome needs a run-like object with .status
        class RunLike:
            def __init__(self, status: RemediationRunStatus):
                self.status = status
        assert allow_update_outcome(RunLike(RemediationRunStatus.pending)) is True
        assert allow_update_outcome(RunLike(RemediationRunStatus.success)) is False
        ok.append("Remediation audit guards: is_run_completed, allow_update_outcome OK")
    except Exception as e:
        errors.append(f"Remediation audit guards: {e}")

    # 3. SQS remediation_run payload
    try:
        from backend.utils.sqs import (
            REMEDIATION_RUN_JOB_TYPE,
            build_remediation_run_job_payload,
        )
        run_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        action_id = uuid.uuid4()
        created_at = "2026-02-02T12:00:00Z"
        payload = build_remediation_run_job_payload(run_id, tenant_id, action_id, "pr_only", created_at)
        assert payload["job_type"] == REMEDIATION_RUN_JOB_TYPE
        assert payload["run_id"] == str(run_id)
        assert payload["tenant_id"] == str(tenant_id)
        assert payload["action_id"] == str(action_id)
        assert payload["mode"] == "pr_only"
        assert payload["created_at"] == created_at
        ok.append("SQS remediation_run payload builder OK")
    except Exception as e:
        errors.append(f"SQS remediation_run payload: {e}")

    # 4. Worker handler registered
    try:
        from backend.utils.sqs import REMEDIATION_RUN_JOB_TYPE
        from backend.workers.jobs import get_job_handler
        handler = get_job_handler(REMEDIATION_RUN_JOB_TYPE)
        assert handler is not None, "remediation_run handler should be registered"
        assert callable(handler), "handler should be callable"
        ok.append("Worker remediation_run handler registered OK")
    except Exception as e:
        errors.append(f"Worker handler registration: {e}")

    # 5. Migrations / DB tables (optional; may skip if no DB)
    try:
        from backend.config import settings
        from sqlalchemy import create_engine, text
        url = getattr(settings, "database_url_sync", None)
        if not url:
            url = getattr(settings, "DATABASE_URL_SYNC", None)
        if not url and hasattr(settings, "DATABASE_URL"):
            url = (settings.DATABASE_URL or "").replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
        if url and "postgresql" in url:
            engine = create_engine(url)
            with engine.connect() as conn:
                r = conn.execute(text(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'remediation_runs'"
                ))
                if r.fetchone() is None:
                    errors.append("DB: table remediation_runs not found (run alembic upgrade head)")
                else:
                    ok.append("DB: table remediation_runs exists")
                r2 = conn.execute(text(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'audit_log'"
                ))
                if r2.fetchone() is None:
                    errors.append("DB: table audit_log not found (run alembic upgrade head)")
                else:
                    ok.append("DB: table audit_log exists")
        else:
            ok.append("DB: skip (no DATABASE_URL); run alembic upgrade head if needed")
    except Exception as e:
        errors.append(f"DB check: {e}")

    # Report
    for s in ok:
        print(f"  OK: {s}")
    for s in errors:
        print(f"  FAIL: {s}", file=sys.stderr)
    if errors:
        print(f"\n{len(errors)} check(s) failed. See docs/step7-verification.md for full verification.", file=sys.stderr)
        return 1
    print(f"\nAll {len(ok)} Step 7 checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
