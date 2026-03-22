RAW DIRECT-FIX EXTRACTION

> Historical raw extraction note: this file preserves the pre-2026-03-19 direct-fix implementation inventory. Current `master` keeps the underlying modules on disk for future re-scoping, but the active product contract is PR-only and customer `WriteRole` is out of scope.

| Control ID or Action ID | AWS Service | API Operation | boto3 Call | Source File | Source Line |
|------------------------|------------|--------------|------------|-------------|-------------|
| s3_block_public_access | s3control | put_public_access_block | `s3c.put_public_access_block(...)` | `backend/workers/services/direct_fix.py` | 327 |
| enable_security_hub | securityhub | enable_security_hub | `sh.enable_security_hub(EnableDefaultStandards=True)` | `backend/workers/services/direct_fix.py` | 427 |
| enable_guardduty | guardduty | create_detector | `gd.create_detector(Enable=True)` | `backend/workers/services/direct_fix.py` | 514 |
| enable_guardduty | guardduty | update_detector | `gd.update_detector(DetectorId=detector_id, Enable=True)` | `backend/workers/services/direct_fix.py` | 531 |
| ebs_default_encryption | ec2 | enable_ebs_encryption_by_default | `ec2.enable_ebs_encryption_by_default()` | `backend/workers/services/direct_fix.py` | 627 |
| ebs_default_encryption | ec2 | modify_ebs_default_kms_key_id | `ec2.modify_ebs_default_kms_key_id(KmsKeyId=desired_kms)` | `backend/workers/services/direct_fix.py` | 630 |

Files read and line counts
- `alembic/versions/0007_remediation_runs_table.py` — 92 lines — no direct-fix API calls.
- `alembic/versions/0020_remediation_run_executions.py` — 94 lines — no direct-fix API calls.
- `backend/models/remediation_run.py` — 80 lines — no direct-fix API calls.
- `backend/models/remediation_run_execution.py` — 69 lines — no direct-fix API calls.
- `backend/routers/remediation_runs.py` — 2675 lines — no direct-fix API calls that resolve findings (SQS/API orchestration only).
- `backend/services/direct_fix_bridge.py` — 48 lines — no direct-fix API calls (bridge/import wrapper only).
- `backend/services/remediation_audit.py` — 101 lines — no direct-fix API calls.
- `backend/services/remediation_metrics.py` — 83 lines — no direct-fix API calls.
- `backend/services/remediation_risk.py` — 464 lines — no direct-fix API calls.
- `backend/services/remediation_runtime_checks.py` — 436 lines — no direct-fix API calls (read-only probes/checks only).
- `backend/services/remediation_strategy.py` — 611 lines — no direct-fix API calls.
- `backend/workers/jobs/remediation_run.py` — 1254 lines — no direct-fix API calls that resolve findings (worker orchestration only).
- `backend/workers/jobs/remediation_run_execution.py` — 682 lines — no direct-fix API calls.
- `backend/workers/services/control_plane_events.py` — 483 lines — no direct-fix API calls that resolve findings (ingest/normalization logic).
- `backend/workers/services/direct_fix.py` — 662 lines — contains direct-fix API calls (extracted above).
- `backend/workers/services/inventory_assets.py` — 97 lines — no direct-fix API calls.
- `backend/workers/services/inventory_reconcile.py` — 1479 lines — no direct-fix API calls that resolve findings (inventory collection/reconcile logic).
- `backend/workers/services/json_safe.py` — 48 lines — no direct-fix API calls.
- `docs/audit-remediation/phase2-architecture-closure-checklist.md` — 120 lines — no direct-fix API calls.
- `docs/audit-remediation/phase3-architecture-closure-checklist.md` — 159 lines — no direct-fix API calls.
- `docs/audit-remediation/phase3-security-closure-checklist.md` — 161 lines — no direct-fix API calls.
- `docs/audit-remediation/phase4-required-check-governance.md` — 66 lines — no direct-fix API calls.
- `docs/remediation-safety-model.md` — 134 lines — no direct-fix API calls.
- `tests/test_direct_fix.py` — 369 lines — no product direct-fix API calls (test doubles/mocks only).
- `tests/test_remediation_risk.py` — 139 lines — no direct-fix API calls.
- `tests/test_remediation_run_execution.py` — 197 lines — no product direct-fix API calls (test mocks only).
- `tests/test_remediation_run_worker.py` — 966 lines — no product direct-fix API calls (test mocks only).
- `tests/test_remediation_runs_api.py` — 1455 lines — no product direct-fix API calls (test mocks only).

Output file write confirmation: written to `docs/prod-readiness/06-task5-raw-direct-fix.md`.
Output file line count: 42
