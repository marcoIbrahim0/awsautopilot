---
Test 02 — Database Connectivity and Migration State
Run date: 2026-02-27
Status: PASS

ENVIRONMENT VALUES (used by all subsequent tests)
FRONTEND_URL=https://dev.valensjewelry.com
BACKEND_API_URL=https://api.valensjewelry.com
TEST_EMAIL=maromaher54@gmail.com
TEST_PASSWORD=Maher730
ADMIN_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1N2U2NThkOS1kNWMxLTQ3OGEtODFmOC04Y2YwNDAwZDAwMWUiLCJ0ZW5hbnRfaWQiOiIxOWI4ZDdjNi0wMTAwLTQyMWEtYTA4NC1jOGIwNmQ0NjY4MzciLCJleHAiOjE3NzI4MzcwOTB9.XKImRpmOQ-dLZHD1UxSqTq5Kw2oL1z7fI-MovGfeo00

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 2.1 Database connection from API | No DB connection errors in startup/log output | `GET /health` returned HTTP 200; API CloudWatch log scan (`/aws/lambda/security-autopilot-dev-api`, last 24h) showed no DB connection errors (`database`, `psycopg`, `sqlalchemy`, `alembic`, `Refusing to start api`) | PASS |
| 2.2 Migration state is current | current revision matches head revision | `alembic -c alembic.ini current` -> `0032_findings_resolved_at (head)` and `alembic -c alembic.ini heads` -> `0032_findings_resolved_at (head)` | PASS |
| 2.3 No failed migrations in history | clean linear history with no gaps/failures | `alembic -c alembic.ini history --verbose` showed a linear chain from `0001_initial_models` to `0032_findings_resolved_at` with no broken parent links or failed revisions | PASS |
| 2.4 Core tables exist | users, tenants, aws_accounts, findings, actions, remediation_runs, exports, audit_log | Present: `users`, `tenants`, `aws_accounts`, `findings`, `actions`, `remediation_runs`, `audit_log`; export table is implemented as `evidence_exports` (table `exports` not present) | PASS |
| 2.5 No orphaned pending jobs | no `remediation_runs` with `status='pending'` older than 1 hour | SQL check returned `PENDING_OLDER_THAN_1H=0` | PASS |

Failed tests:
* None

Blocking for go-live: no
Notes: API logs include repeated S3 template list `AccessDenied` errors and `INIT_REPORT ... timeout` entries, but no database connection failures were observed during this test.
---
