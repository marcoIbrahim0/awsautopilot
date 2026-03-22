# Task 7 Implementation Status Classification

> Historical note (2026-03-15): Public SaaS-managed PR-bundle plan/apply is archived. Customer-run PR bundles remain supported; the tables below reflect the February 2026 snapshot, not the current product direction.

Audit source preflight result: `docs/prod-readiness/02-audit-security-backend.md`, `03-audit-reliability-observability.md`, and `04-audit-deployment-frontend-compliance.md` are missing. Audit-dependent broken-state judgments are treated as `unknown (audit source missing)`.

FEATURE IMPLEMENTATION STATUS MASTER TABLE
| Feature ID | Feature Name | Category | Status | Evidence for status (file and line or audit finding ID) | What is missing or broken (one sentence) | Blocking for GA (yes / no) |
|---|---|---|---|---|---|---|
| FE-001 | Root auth router | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:4 | No known implementation gap from repository evidence. | no |
| FE-002 | Marketing site nav + hero CTAs | frontend | PARTIAL | docs/features/feat-task2-frontend-features.md:5 | Contains TODO placeholders for some marketing assets/links. | no |
| FE-003 | FAQ accordion | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:6 | No known implementation gap from repository evidence. | no |
| FE-004 | Contact popover panel | frontend | STUB | docs/features/feat-task2-frontend-features.md:7 | UI placeholder exists, but no production backend behavior is wired. | no |
| FE-005 | Locale dropdown | frontend | STUB | docs/features/feat-task2-frontend-features.md:8 | UI placeholder exists, but no production backend behavior is wired. | no |
| FE-006 | Login | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:9 | No known implementation gap from repository evidence. | no |
| FE-007 | Forgot password request | frontend | MISSING | frontend/src/lib/api.ts:2802; backend/routers/auth.py:124,220,292,304,353,385 | Password-reset request API route is not implemented, so the flow cannot start. | yes |
| FE-008 | Signup | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:11 | No known implementation gap from repository evidence. | no |
| FE-009 | Accept invite | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:12 | No known implementation gap from repository evidence. | no |
| FE-010 | Reset password | frontend | MISSING | frontend/src/lib/api.ts:2809; backend/routers/auth.py:124,220,292,304,353,385 | Password-reset completion API route is not implemented, so reset tokens cannot be applied. | yes |
| FE-011 | Session expiry recovery | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:14 | No known implementation gap from repository evidence. | no |
| FE-012 | Global 404 page | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:15 | No known implementation gap from repository evidence. | no |
| FE-013 | Global error boundary | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:16 | No known implementation gap from repository evidence. | no |
| FE-014 | Sidebar navigation shell | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:17 | No known implementation gap from repository evidence. | no |
| FE-015 | Top bar notifications and profile menu | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:18 | No known implementation gap from repository evidence. | no |
| FE-016 | Global async banner rail | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:19 | No known implementation gap from repository evidence. | no |
| FE-017 | Accounts list + sectional views | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:20 | No known implementation gap from repository evidence. | no |
| FE-018 | Connect/reconnect AWS account | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:21 | No known implementation gap from repository evidence. | no |
| FE-019 | Copy onboarding identifiers in connect modal | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:22 | No known implementation gap from repository evidence. | no |
| FE-020 | Validate account role | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:23 | No known implementation gap from repository evidence. | no |
| FE-021 | Stop/resume monitoring | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:24 | No known implementation gap from repository evidence. | no |
| FE-022 | Remove account | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:25 | No known implementation gap from repository evidence. | no |
| FE-023 | Ingest refresh by source | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:26 | No known implementation gap from repository evidence. | no |
| FE-024 | Ingest refresh all sources | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:27 | No known implementation gap from repository evidence. | no |
| FE-025 | Ingest progress polling | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:28 | No known implementation gap from repository evidence. | no |
| FE-026 | Reconciliation preflight/run | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:29 | No known implementation gap from repository evidence. | no |
| FE-027 | Reconciliation schedule management | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:30 | No known implementation gap from repository evidence. | no |
| FE-028 | Service verification shortcut | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:31 | No known implementation gap from repository evidence. | no |
| FE-029 | Onboarding stepper + autosave draft | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:32 | No known implementation gap from repository evidence. | no |
| FE-030 | Launch-stack role setup links | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:33 | No known implementation gap from repository evidence. | no |
| FE-031 | Validate integration role | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:34 | No known implementation gap from repository evidence. | no |
| FE-032 | Service readiness checks | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:35 | No known implementation gap from repository evidence. | no |
| FE-033 | Control-plane readiness check | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:36 | No known implementation gap from repository evidence. | no |
| FE-034 | Control-plane token rotate/revoke | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:37; backend/routers/auth.py:353,385 | No known implementation gap from repository evidence. | no |
| FE-035 | Fast-path onboarding trigger | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:38 | No known implementation gap from repository evidence. | no |
| FE-036 | Final checks + queue initial workload | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:39 | No known implementation gap from repository evidence. | no |
| FE-037 | Findings filters and source/severity tabs | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:40 | No known implementation gap from repository evidence. | no |
| FE-038 | Grouped findings mode | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:41 | No known implementation gap from repository evidence. | no |
| FE-039 | Group-level actions on findings | frontend | MISSING | frontend/src/lib/api.ts:833; backend/routers/findings.py:442,543,685 | Group-action API route is missing, so suppress/acknowledge/false-positive bulk actions cannot execute. | no |
| FE-040 | Shared-resource safety confirmation | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:43 | No known implementation gap from repository evidence. | no |
| FE-041 | First-run processing tracker | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:44 | No known implementation gap from repository evidence. | no |
| FE-042 | Retry first-run processing | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:45 | No known implementation gap from repository evidence. | no |
| FE-043 | Findings pagination | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:46 | No known implementation gap from repository evidence. | no |
| FE-044 | Finding detail page | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:47 | No known implementation gap from repository evidence. | no |
| FE-045 | Action detail drawer | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:48 | No known implementation gap from repository evidence. | no |
| FE-046 | Recompute actions from drawer | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:49 | No known implementation gap from repository evidence. | no |
| FE-047 | Remediation strategy selection | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:50 | No known implementation gap from repository evidence. | no |
| FE-048 | Manual workflow evidence upload | frontend | MISSING | frontend/src/lib/api.ts:1626,1639,1659,1674; backend/routers/actions.py:385,616,676,790,934,1018 | Manual-workflow evidence and validation routes are not implemented, so required evidence handling cannot run. | yes |
| FE-049 | Create remediation run | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:52 | No known implementation gap from repository evidence. | no |
| FE-050 | Create exception modal | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:53 | No known implementation gap from repository evidence. | no |
| FE-051 | Action-group persistent view | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:54 | No known implementation gap from repository evidence. | no |
| FE-052 | Action-group bundle run generation | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:55 | No known implementation gap from repository evidence. | no |
| FE-053 | Action-group bundle download | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:56 | No known implementation gap from repository evidence. | no |
| FE-054 | Top-risks dashboard | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:57 | No known implementation gap from repository evidence. | no |
| FE-055 | Exceptions list and filtering | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:58 | No known implementation gap from repository evidence. | no |
| FE-056 | Revoke exception | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:59 | No known implementation gap from repository evidence. | no |
| FE-057 | Evidence/compliance export creation | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:60 | No known implementation gap from repository evidence. | no |
| FE-058 | Export history and ad-hoc download | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:61 | No known implementation gap from repository evidence. | no |
| FE-059 | Baseline report request from exports tab | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:62 | No known implementation gap from repository evidence. | no |
| FE-060 | Baseline report viewer page | frontend | PARTIAL | frontend/src/lib/api.ts:2106; backend/routers/baseline_report.py:129,267,312 | Detailed report data endpoint (`/api/baseline-report/{report_id}/data`) is missing, so full baseline-report rendering is incomplete. | no |
| FE-061 | Support files download center | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:64 | No known implementation gap from repository evidence. | no |
| FE-062 | Audit log explorer | frontend | MISSING | frontend/src/lib/api.ts:1329; docs/features/feat-task3-backend-features.md:5-119 | Audit-log API route is not implemented, so admin audit-log queries cannot be served. | yes |
| FE-063 | PR bundle history | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:66 | No known implementation gap from repository evidence. | no |
| FE-064 | PR bundle action picker | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:67 | No known implementation gap from repository evidence. | no |
| FE-065 | PR bundle summary generation | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:68 | No known implementation gap from repository evidence. | no |
| FE-066 | Online execution controls for generated bundles | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:69 | No known implementation gap from repository evidence. | no |
| FE-067 | Remediation run live status | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:70 | No known implementation gap from repository evidence. | no |
| FE-068 | Cancel remediation run | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:71 | No known implementation gap from repository evidence. | no |
| FE-069 | Resend stale remediation run | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:72 | No known implementation gap from repository evidence. | no |
| FE-070 | Download generated PR files from run | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:73 | No known implementation gap from repository evidence. | no |
| FE-071 | Settings profile update | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:74 | No known implementation gap from repository evidence. | no |
| FE-072 | Email/phone verification modal | frontend | MISSING | frontend/src/lib/api.ts:2783,2795; backend/routers/auth.py:124,220,292,304,353,385 | Verification send/confirm API routes are not implemented, so email/phone verification cannot complete. | no |
| FE-073 | Settings password management | frontend | MISSING | frontend/src/lib/api.ts:2772,2802; backend/routers/auth.py:124,220,292,304,353,385 | Password-change and forgot-password API routes are not implemented, so settings password management is non-functional. | yes |
| FE-074 | Settings account deletion | frontend | MISSING | frontend/src/lib/api.ts:2761; backend/routers/users.py:412,576 | Self-delete API route (`DELETE /api/users/me`) is missing; only admin delete-by-user-id is implemented. | no |
| FE-075 | Team invite | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:78 | No known implementation gap from repository evidence. | no |
| FE-076 | Team member removal | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:79 | No known implementation gap from repository evidence. | no |
| FE-077 | Digest notification settings | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:80 | No known implementation gap from repository evidence. | no |
| FE-078 | Slack notification settings | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:81 | No known implementation gap from repository evidence. | no |
| FE-079 | Settings evidence export panel | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:82 | No known implementation gap from repository evidence. | no |
| FE-080 | Control mappings management | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:83 | No known implementation gap from repository evidence. | no |
| FE-081 | Settings baseline report panel | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:84 | No known implementation gap from repository evidence. | no |
| FE-082 | Organization readiness + launch workflow | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:85 | No known implementation gap from repository evidence. | no |
| FE-083 | SaaS admin tenant list | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:86 | No known implementation gap from repository evidence. | no |
| FE-084 | SaaS admin tenant detail workspace | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:87 | No known implementation gap from repository evidence. | no |
| FE-085 | Admin support note creation | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:88 | No known implementation gap from repository evidence. | no |
| FE-086 | Admin support file upload | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:89 | No known implementation gap from repository evidence. | no |
| FE-087 | Control-plane global ops dashboard | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:90 | No known implementation gap from repository evidence. | no |
| FE-088 | Control-plane tenant drilldown | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:91 | No known implementation gap from repository evidence. | no |
| FE-089 | Control-plane reconcile enqueue actions | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:92 | No known implementation gap from repository evidence. | no |
| FE-090 | Control-plane reconcile job history | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:93 | No known implementation gap from repository evidence. | no |
| FE-091 | Legacy actions route redirect | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:94 | No known implementation gap from repository evidence. | no |
| FE-092 | Legacy action-detail route redirect | frontend | COMPLETE | docs/features/feat-task2-frontend-features.md:95 | No known implementation gap from repository evidence. | no |
| API-001 | GET /api/action-groups | api | COMPLETE | docs/features/feat-task3-backend-features.md:5 | No known implementation gap from repository evidence. | no |
| API-002 | GET /api/action-groups/{group_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:6 | No known implementation gap from repository evidence. | no |
| API-003 | GET /api/action-groups/{group_id}/runs | api | COMPLETE | docs/features/feat-task3-backend-features.md:7 | No known implementation gap from repository evidence. | no |
| API-004 | POST /api/action-groups/{group_id}/bundle-run | api | COMPLETE | docs/features/feat-task3-backend-features.md:8 | No known implementation gap from repository evidence. | no |
| API-005 | GET /api/actions | api | COMPLETE | docs/features/feat-task3-backend-features.md:9 | No known implementation gap from repository evidence. | no |
| API-006 | GET /api/actions/{action_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:10 | No known implementation gap from repository evidence. | no |
| API-007 | GET /api/actions/{action_id}/remediation-options | api | COMPLETE | docs/features/feat-task3-backend-features.md:11 | No known implementation gap from repository evidence. | no |
| API-008 | GET /api/actions/{action_id}/remediation-preview | api | COMPLETE | docs/features/feat-task3-backend-features.md:12 | No known implementation gap from repository evidence. | no |
| API-009 | PATCH /api/actions/{action_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:13 | No known implementation gap from repository evidence. | no |
| API-010 | POST /api/actions/compute | api | COMPLETE | docs/features/feat-task3-backend-features.md:14 | No known implementation gap from repository evidence. | no |
| API-011 | POST /api/auth/signup | api | COMPLETE | docs/features/feat-task3-backend-features.md:15 | No known implementation gap from repository evidence. | no |
| API-012 | POST /api/auth/login | api | COMPLETE | docs/features/feat-task3-backend-features.md:16 | No known implementation gap from repository evidence. | no |
| API-013 | POST /api/auth/logout | api | COMPLETE | docs/features/feat-task3-backend-features.md:17 | No known implementation gap from repository evidence. | no |
| API-014 | GET /api/auth/me | api | COMPLETE | docs/features/feat-task3-backend-features.md:18 | No known implementation gap from repository evidence. | no |
| API-015 | POST /api/auth/control-plane-token/rotate | api | COMPLETE | docs/features/feat-task3-backend-features.md:19 | No known implementation gap from repository evidence. | no |
| API-016 | POST /api/auth/control-plane-token/revoke | api | COMPLETE | docs/features/feat-task3-backend-features.md:20 | No known implementation gap from repository evidence. | no |
| API-017 | GET /api/aws/accounts | api | COMPLETE | docs/features/feat-task3-backend-features.md:21 | No known implementation gap from repository evidence. | no |
| API-018 | PATCH /api/aws/accounts/{account_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:22 | No known implementation gap from repository evidence. | no |
| API-019 | DELETE /api/aws/accounts/{account_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:23 | No known implementation gap from repository evidence. | no |
| API-020 | POST /api/aws/accounts/{account_id}/read-role/update | api | COMPLETE | docs/features/feat-task3-backend-features.md:24 | No known implementation gap from repository evidence. | no |
| API-021 | GET /api/aws/accounts/{account_id}/read-role/update-status | api | COMPLETE | docs/features/feat-task3-backend-features.md:25 | No known implementation gap from repository evidence. | no |
| API-022 | POST /api/aws/accounts | api | COMPLETE | docs/features/feat-task3-backend-features.md:26 | No known implementation gap from repository evidence. | no |
| API-023 | POST /api/aws/accounts/{account_id}/validate | api | COMPLETE | docs/features/feat-task3-backend-features.md:27 | No known implementation gap from repository evidence. | no |
| API-024 | POST /api/aws/accounts/{account_id}/service-readiness | api | COMPLETE | docs/features/feat-task3-backend-features.md:28 | No known implementation gap from repository evidence. | no |
| API-025 | POST /api/aws/accounts/{account_id}/onboarding-fast-path | api | COMPLETE | docs/features/feat-task3-backend-features.md:29 | No known implementation gap from repository evidence. | no |
| API-026 | GET /api/aws/accounts/{account_id}/control-plane-readiness | api | COMPLETE | docs/features/feat-task3-backend-features.md:30 | No known implementation gap from repository evidence. | no |
| API-027 | POST /api/aws/accounts/{account_id}/ingest | api | COMPLETE | docs/features/feat-task3-backend-features.md:31 | No known implementation gap from repository evidence. | no |
| API-028 | GET /api/aws/accounts/{account_id}/ingest-progress | api | COMPLETE | docs/features/feat-task3-backend-features.md:32 | No known implementation gap from repository evidence. | no |
| API-029 | POST /api/aws/accounts/{account_id}/ingest-access-analyzer | api | COMPLETE | docs/features/feat-task3-backend-features.md:33 | No known implementation gap from repository evidence. | no |
| API-030 | POST /api/aws/accounts/{account_id}/ingest-inspector | api | COMPLETE | docs/features/feat-task3-backend-features.md:34 | No known implementation gap from repository evidence. | no |
| API-031 | POST /api/aws/accounts/{account_id}/ingest-sync | api | PARTIAL | docs/features/feat-task3-backend-features.md:35; backend/routers/aws_accounts.py:1252 | Synchronous ingest exists, but it bypasses the primary SQS/worker flow and remains a non-primary path. | no |
| API-032 | GET /api/aws/accounts/ping | api | COMPLETE | docs/features/feat-task3-backend-features.md:36 | No known implementation gap from repository evidence. | no |
| API-033 | POST /api/baseline-report | api | COMPLETE | docs/features/feat-task3-backend-features.md:37 | No known implementation gap from repository evidence. | no |
| API-034 | GET /api/baseline-report | api | COMPLETE | docs/features/feat-task3-backend-features.md:38 | No known implementation gap from repository evidence. | no |
| API-035 | GET /api/baseline-report/{report_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:39 | No known implementation gap from repository evidence. | no |
| API-036 | GET /api/control-mappings | api | COMPLETE | docs/features/feat-task3-backend-features.md:40 | No known implementation gap from repository evidence. | no |
| API-037 | GET /api/control-mappings/{mapping_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:41 | No known implementation gap from repository evidence. | no |
| API-038 | POST /api/control-mappings | api | COMPLETE | docs/features/feat-task3-backend-features.md:42 | No known implementation gap from repository evidence. | no |
| API-039 | POST /api/control-plane/events | api | COMPLETE | docs/features/feat-task3-backend-features.md:43 | No known implementation gap from repository evidence. | no |
| API-040 | POST /api/exceptions | api | COMPLETE | docs/features/feat-task3-backend-features.md:44 | No known implementation gap from repository evidence. | no |
| API-041 | GET /api/exceptions | api | COMPLETE | docs/features/feat-task3-backend-features.md:45 | No known implementation gap from repository evidence. | no |
| API-042 | GET /api/exceptions/{exception_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:46 | No known implementation gap from repository evidence. | no |
| API-043 | DELETE /api/exceptions/{exception_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:47 | No known implementation gap from repository evidence. | no |
| API-044 | POST /api/exports | api | COMPLETE | docs/features/feat-task3-backend-features.md:48 | No known implementation gap from repository evidence. | no |
| API-045 | GET /api/exports | api | COMPLETE | docs/features/feat-task3-backend-features.md:49 | No known implementation gap from repository evidence. | no |
| API-046 | GET /api/exports/{export_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:50 | No known implementation gap from repository evidence. | no |
| API-047 | GET /api/findings/grouped | api | COMPLETE | docs/features/feat-task3-backend-features.md:51 | No known implementation gap from repository evidence. | no |
| API-048 | GET /api/findings | api | COMPLETE | docs/features/feat-task3-backend-features.md:52 | No known implementation gap from repository evidence. | no |
| API-049 | GET /api/findings/{finding_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:53 | No known implementation gap from repository evidence. | no |
| API-050 | POST /api/internal/weekly-digest | api | COMPLETE | docs/features/feat-task3-backend-features.md:54 | No known implementation gap from repository evidence. | no |
| API-051 | POST /api/internal/control-plane-events | api | COMPLETE | docs/features/feat-task3-backend-features.md:55 | No known implementation gap from repository evidence. | no |
| API-052 | POST /api/internal/reconcile-inventory-shard | api | COMPLETE | docs/features/feat-task3-backend-features.md:56 | No known implementation gap from repository evidence. | no |
| API-053 | POST /api/internal/reconcile-recently-touched | api | COMPLETE | docs/features/feat-task3-backend-features.md:57 | No known implementation gap from repository evidence. | no |
| API-054 | POST /api/internal/group-runs/report | api | COMPLETE | docs/features/feat-task3-backend-features.md:58 | No known implementation gap from repository evidence. | no |
| API-055 | POST /api/internal/reconcile-inventory-global | api | COMPLETE | docs/features/feat-task3-backend-features.md:59 | No known implementation gap from repository evidence. | no |
| API-056 | POST /api/internal/reconcile-inventory-global-all-tenants | api | COMPLETE | docs/features/feat-task3-backend-features.md:60 | No known implementation gap from repository evidence. | no |
| API-057 | POST /api/internal/reconciliation/schedule-tick | api | COMPLETE | docs/features/feat-task3-backend-features.md:61 | No known implementation gap from repository evidence. | no |
| API-058 | POST /api/internal/backfill-finding-keys | api | COMPLETE | docs/features/feat-task3-backend-features.md:62 | No known implementation gap from repository evidence. | no |
| API-059 | POST /api/internal/backfill-action-groups | api | COMPLETE | docs/features/feat-task3-backend-features.md:63 | No known implementation gap from repository evidence. | no |
| API-060 | GET /api/meta/scope | api | COMPLETE | docs/features/feat-task3-backend-features.md:64 | No known implementation gap from repository evidence. | no |
| API-061 | POST /api/reconciliation/preflight | api | COMPLETE | docs/features/feat-task3-backend-features.md:65 | No known implementation gap from repository evidence. | no |
| API-062 | POST /api/reconciliation/run | api | COMPLETE | docs/features/feat-task3-backend-features.md:66 | No known implementation gap from repository evidence. | no |
| API-063 | GET /api/reconciliation/status | api | COMPLETE | docs/features/feat-task3-backend-features.md:67 | No known implementation gap from repository evidence. | no |
| API-064 | GET /api/reconciliation/coverage | api | COMPLETE | docs/features/feat-task3-backend-features.md:68 | No known implementation gap from repository evidence. | no |
| API-065 | GET /api/reconciliation/settings/{account_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:69 | No known implementation gap from repository evidence. | no |
| API-066 | PUT /api/reconciliation/settings/{account_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:70 | No known implementation gap from repository evidence. | no |
| API-067 | POST /api/remediation-runs | api | COMPLETE | docs/features/feat-task3-backend-features.md:71 | No known implementation gap from repository evidence. | no |
| API-068 | POST /api/remediation-runs/group-pr-bundle | api | COMPLETE | docs/features/feat-task3-backend-features.md:72 | No known implementation gap from repository evidence. | no |
| API-069 | GET /api/remediation-runs | api | COMPLETE | docs/features/feat-task3-backend-features.md:73 | No known implementation gap from repository evidence. | no |
| API-070 | PATCH /api/remediation-runs/{run_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:74 | No known implementation gap from repository evidence. | no |
| API-071 | GET /api/remediation-runs/{run_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:75 | No known implementation gap from repository evidence. | no |
| API-072 | POST /api/remediation-runs/bulk-execute-pr-bundle | api | COMPLETE | docs/features/feat-task3-backend-features.md:76 | No known implementation gap from repository evidence. | no |
| API-073 | POST /api/remediation-runs/bulk-approve-apply | api | COMPLETE | docs/features/feat-task3-backend-features.md:77 | No known implementation gap from repository evidence. | no |
| API-074 | POST /api/remediation-runs/{run_id}/execute-pr-bundle | api | COMPLETE | docs/features/feat-task3-backend-features.md:78 | No known implementation gap from repository evidence. | no |
| API-075 | POST /api/remediation-runs/{run_id}/approve-apply | api | COMPLETE | docs/features/feat-task3-backend-features.md:79 | No known implementation gap from repository evidence. | no |
| API-076 | GET /api/remediation-runs/{run_id}/execution | api | COMPLETE | docs/features/feat-task3-backend-features.md:80 | No known implementation gap from repository evidence. | no |
| API-077 | POST /api/remediation-runs/{run_id}/resend | api | COMPLETE | docs/features/feat-task3-backend-features.md:81 | No known implementation gap from repository evidence. | no |
| API-078 | GET /api/remediation-runs/{run_id}/pr-bundle.zip | api | COMPLETE | docs/features/feat-task3-backend-features.md:82 | No known implementation gap from repository evidence. | no |
| API-079 | GET /api/saas/system-health | api | COMPLETE | docs/features/feat-task3-backend-features.md:83 | No known implementation gap from repository evidence. | no |
| API-080 | GET /api/saas/control-plane/slo | api | COMPLETE | docs/features/feat-task3-backend-features.md:84 | No known implementation gap from repository evidence. | no |
| API-081 | GET /api/saas/control-plane/shadow-summary | api | COMPLETE | docs/features/feat-task3-backend-features.md:85 | No known implementation gap from repository evidence. | no |
| API-082 | GET /api/saas/control-plane/shadow-compare | api | COMPLETE | docs/features/feat-task3-backend-features.md:86 | No known implementation gap from repository evidence. | no |
| API-083 | GET /api/saas/control-plane/compare | api | COMPLETE | docs/features/feat-task3-backend-features.md:87 | No known implementation gap from repository evidence. | no |
| API-084 | GET /api/saas/control-plane/unmatched-report | api | COMPLETE | docs/features/feat-task3-backend-features.md:88 | No known implementation gap from repository evidence. | no |
| API-085 | GET /api/saas/control-plane/reconcile-jobs | api | COMPLETE | docs/features/feat-task3-backend-features.md:89 | No known implementation gap from repository evidence. | no |
| API-086 | POST /api/saas/control-plane/reconcile/recently-touched | api | COMPLETE | docs/features/feat-task3-backend-features.md:90 | No known implementation gap from repository evidence. | no |
| API-087 | POST /api/saas/control-plane/reconcile/global | api | COMPLETE | docs/features/feat-task3-backend-features.md:91 | No known implementation gap from repository evidence. | no |
| API-088 | POST /api/saas/control-plane/reconcile/shard | api | COMPLETE | docs/features/feat-task3-backend-features.md:92 | No known implementation gap from repository evidence. | no |
| API-089 | GET /api/saas/tenants | api | COMPLETE | docs/features/feat-task3-backend-features.md:93 | No known implementation gap from repository evidence. | no |
| API-090 | GET /api/saas/tenants/{tenant_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:94 | No known implementation gap from repository evidence. | no |
| API-091 | GET /api/saas/tenants/{tenant_id}/users | api | COMPLETE | docs/features/feat-task3-backend-features.md:95 | No known implementation gap from repository evidence. | no |
| API-092 | GET /api/saas/tenants/{tenant_id}/aws-accounts | api | COMPLETE | docs/features/feat-task3-backend-features.md:96 | No known implementation gap from repository evidence. | no |
| API-093 | GET /api/saas/tenants/{tenant_id}/findings | api | COMPLETE | docs/features/feat-task3-backend-features.md:97 | No known implementation gap from repository evidence. | no |
| API-094 | GET /api/saas/tenants/{tenant_id}/actions | api | COMPLETE | docs/features/feat-task3-backend-features.md:98 | No known implementation gap from repository evidence. | no |
| API-095 | GET /api/saas/tenants/{tenant_id}/remediation-runs | api | COMPLETE | docs/features/feat-task3-backend-features.md:99 | No known implementation gap from repository evidence. | no |
| API-096 | GET /api/saas/tenants/{tenant_id}/exports | api | COMPLETE | docs/features/feat-task3-backend-features.md:100 | No known implementation gap from repository evidence. | no |
| API-097 | GET /api/saas/tenants/{tenant_id}/baseline-reports | api | COMPLETE | docs/features/feat-task3-backend-features.md:101 | No known implementation gap from repository evidence. | no |
| API-098 | GET /api/saas/tenants/{tenant_id}/notes | api | COMPLETE | docs/features/feat-task3-backend-features.md:102 | No known implementation gap from repository evidence. | no |
| API-099 | POST /api/saas/tenants/{tenant_id}/notes | api | COMPLETE | docs/features/feat-task3-backend-features.md:103 | No known implementation gap from repository evidence. | no |
| API-100 | GET /api/saas/tenants/{tenant_id}/files | api | COMPLETE | docs/features/feat-task3-backend-features.md:104 | No known implementation gap from repository evidence. | no |
| API-101 | POST /api/saas/tenants/{tenant_id}/files/initiate | api | COMPLETE | docs/features/feat-task3-backend-features.md:105 | No known implementation gap from repository evidence. | no |
| API-102 | POST /api/saas/tenants/{tenant_id}/files/{file_id}/finalize | api | COMPLETE | docs/features/feat-task3-backend-features.md:106 | No known implementation gap from repository evidence. | no |
| API-103 | POST /api/saas/tenants/{tenant_id}/files/upload | api | COMPLETE | docs/features/feat-task3-backend-features.md:107 | No known implementation gap from repository evidence. | no |
| API-104 | GET /api/support-files | api | COMPLETE | docs/features/feat-task3-backend-features.md:108 | No known implementation gap from repository evidence. | no |
| API-105 | GET /api/support-files/{file_id}/download | api | COMPLETE | docs/features/feat-task3-backend-features.md:109 | No known implementation gap from repository evidence. | no |
| API-106 | GET /api/users | api | COMPLETE | docs/features/feat-task3-backend-features.md:110 | No known implementation gap from repository evidence. | no |
| API-107 | POST /api/users/invite | api | COMPLETE | docs/features/feat-task3-backend-features.md:111 | No known implementation gap from repository evidence. | no |
| API-108 | GET /api/users/accept-invite | api | COMPLETE | docs/features/feat-task3-backend-features.md:112 | No known implementation gap from repository evidence. | no |
| API-109 | POST /api/users/accept-invite | api | COMPLETE | docs/features/feat-task3-backend-features.md:113 | No known implementation gap from repository evidence. | no |
| API-110 | PATCH /api/users/me | api | COMPLETE | docs/features/feat-task3-backend-features.md:114 | No known implementation gap from repository evidence. | no |
| API-111 | GET /api/users/me/digest-settings | api | COMPLETE | docs/features/feat-task3-backend-features.md:115 | No known implementation gap from repository evidence. | no |
| API-112 | PATCH /api/users/me/digest-settings | api | COMPLETE | docs/features/feat-task3-backend-features.md:116 | No known implementation gap from repository evidence. | no |
| API-113 | GET /api/users/me/slack-settings | api | COMPLETE | docs/features/feat-task3-backend-features.md:117 | No known implementation gap from repository evidence. | no |
| API-114 | PATCH /api/users/me/slack-settings | api | COMPLETE | docs/features/feat-task3-backend-features.md:118 | No known implementation gap from repository evidence. | no |
| API-115 | DELETE /api/users/{user_id} | api | COMPLETE | docs/features/feat-task3-backend-features.md:119 | No known implementation gap from repository evidence. | no |
| JOB-001 | worker_queue_poller | job | COMPLETE | docs/features/feat-task4-worker-features.md:5 | No known implementation gap from repository evidence. | no |
| JOB-002 | worker_lambda_handler | job | COMPLETE | docs/features/feat-task4-worker-features.md:6 | No known implementation gap from repository evidence. | no |
| JOB-003 | ingest_findings | job | COMPLETE | docs/features/feat-task4-worker-features.md:7 | No known implementation gap from repository evidence. | no |
| JOB-004 | ingest_access_analyzer | job | COMPLETE | docs/features/feat-task4-worker-features.md:8 | No known implementation gap from repository evidence. | no |
| JOB-005 | ingest_inspector | job | COMPLETE | docs/features/feat-task4-worker-features.md:9 | No known implementation gap from repository evidence. | no |
| JOB-006 | ingest_control_plane_events | job | COMPLETE | docs/features/feat-task4-worker-features.md:10 | No known implementation gap from repository evidence. | no |
| JOB-007 | compute_actions | job | COMPLETE | docs/features/feat-task4-worker-features.md:11 | No known implementation gap from repository evidence. | no |
| JOB-008 | reconcile_inventory_global_orchestration | job | COMPLETE | docs/features/feat-task4-worker-features.md:12 | No known implementation gap from repository evidence. | no |
| JOB-009 | reconcile_inventory_shard | job | COMPLETE | docs/features/feat-task4-worker-features.md:13 | No known implementation gap from repository evidence. | no |
| JOB-010 | reconcile_recently_touched_resources | job | PARTIAL | docs/features/feat-task4-worker-features.md:14 | Target extraction is currently implemented only for SG/S3 event families. | no |
| JOB-011 | remediation_run | job | COMPLETE | docs/features/feat-task4-worker-features.md:15 | No known implementation gap from repository evidence. | no |
| JOB-012 | execute_pr_bundle_plan | job | COMPLETE | docs/features/feat-task4-worker-features.md:16 | No known implementation gap from repository evidence. | no |
| JOB-013 | execute_pr_bundle_apply | job | COMPLETE | docs/features/feat-task4-worker-features.md:17 | No known implementation gap from repository evidence. | no |
| JOB-014 | generate_export | job | COMPLETE | docs/features/feat-task4-worker-features.md:18 | No known implementation gap from repository evidence. | no |
| JOB-015 | generate_baseline_report | job | COMPLETE | docs/features/feat-task4-worker-features.md:19 | No known implementation gap from repository evidence. | no |
| JOB-016 | weekly_digest | job | COMPLETE | docs/features/feat-task4-worker-features.md:20 | No known implementation gap from repository evidence. | no |
| JOB-017 | backfill_finding_keys | job | COMPLETE | docs/features/feat-task4-worker-features.md:21 | No known implementation gap from repository evidence. | no |
| JOB-018 | backfill_action_groups | job | COMPLETE | docs/features/feat-task4-worker-features.md:22 | No known implementation gap from repository evidence. | no |
| AWS-001 | STS AssumeRole | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:5; `backend/services/aws.py:27-160`; `backend/services/tenant_reconciliation.py:194-205`; `backend/services/remediation_runtime_checks.py:136-145` | No known implementation gap from repository evidence. | no |
| AWS-002 | STS GetCallerIdentity | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:6; `backend/services/aws_account_orchestration.py:94-109`; `backend/routers/aws_accounts.py:1178-1191` | No known implementation gap from repository evidence. | no |
| AWS-003 | SQS SendMessage | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:7; `backend/routers/aws_accounts.py:503-577`; `backend/services/tenant_reconciliation.py:367-429`; `backend/routers/control_plane.py:137-157`; `backend/routers/internal.py:312-495;740-793;895-913;1130-1143;1203-1215` | No known implementation gap from repository evidence. | no |
| AWS-004 | SQS GetQueueAttributes | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:8; `backend/services/health_checks.py:137-187` | No known implementation gap from repository evidence. | no |
| AWS-005 | Security Hub GetFindings | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:9; `backend/workers/services/security_hub.py:66-124`; `backend/services/aws_account_orchestration.py:137-145` | No known implementation gap from repository evidence. | no |
| AWS-006 | Security Hub DescribeHub | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:10; `backend/services/aws_account_orchestration.py:301-315`; `backend/workers/services/inventory_reconcile.py:1414-1435` | No known implementation gap from repository evidence. | no |
| AWS-007 | Security Hub GetEnabledStandards | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:11; `backend/workers/services/direct_fix.py:199-219;400-459`; `backend/services/remediation_runtime_checks.py:163-175` | No known implementation gap from repository evidence. | no |
| AWS-008 | Security Hub EnableSecurityHub | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:12; `backend/workers/services/direct_fix.py:425-436` | No known implementation gap from repository evidence. | no |
| AWS-009 | IAM Access Analyzer ListAnalyzers | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:13; `backend/workers/services/access_analyzer.py:69-103`; `backend/services/aws_account_orchestration.py:339-360` | No known implementation gap from repository evidence. | no |
| AWS-010 | IAM Access Analyzer ListFindings | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:14; `backend/workers/services/access_analyzer.py:113-134` | No known implementation gap from repository evidence. | no |
| AWS-011 | Inspector2 ListFindings | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:15; `backend/workers/services/inspector.py:70-110` | No known implementation gap from repository evidence. | no |
| AWS-012 | Inspector2 BatchGetAccountStatus | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:16; `backend/services/aws_account_orchestration.py:371-389` | No known implementation gap from repository evidence. | no |
| AWS-013 | EC2 DescribeSecurityGroups | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:17; `backend/services/aws_account_orchestration.py:147-153`; `backend/workers/services/inventory_reconcile.py:337-379`; `backend/services/tenant_reconciliation.py:221-223` | No known implementation gap from repository evidence. | no |
| AWS-014 | EC2 DescribeVolumes | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:18; `backend/services/tenant_reconciliation.py:255-257` | No known implementation gap from repository evidence. | no |
| AWS-015 | EC2 DescribeSnapshots | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:19; `backend/services/remediation_runtime_checks.py:404-418` | No known implementation gap from repository evidence. | no |
| AWS-016 | EC2 GetEbsEncryptionByDefault | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:20; `backend/workers/services/inventory_reconcile.py:899-901`; `backend/workers/services/direct_fix.py:261-274;605-622;642-649`; `backend/services/remediation_runtime_checks.py:184-189` | No known implementation gap from repository evidence. | no |
| AWS-017 | EC2 GetEbsDefaultKmsKeyId | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:21; `backend/workers/services/direct_fix.py:268-271;613-617;650-657` | No known implementation gap from repository evidence. | no |
| AWS-018 | EC2 EnableEbsEncryptionByDefault | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:22; `backend/workers/services/direct_fix.py:625-639` | No known implementation gap from repository evidence. | no |
| AWS-019 | EC2 ModifyEbsDefaultKmsKeyId | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:23; `backend/workers/services/direct_fix.py:629-631` | No known implementation gap from repository evidence. | no |
| AWS-020 | EC2 GetSnapshotBlockPublicAccessState | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:24; `backend/workers/services/inventory_reconcile.py:907-920` | No known implementation gap from repository evidence. | no |
| AWS-021 | S3 ListBuckets | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:25; `backend/services/aws_account_orchestration.py:155-164`; `backend/workers/services/inventory_reconcile.py:490-495`; `backend/services/tenant_reconciliation.py:224-249` | No known implementation gap from repository evidence. | no |
| AWS-022 | S3 GetBucketLocation | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:26; `backend/workers/services/inventory_reconcile.py:129-140`; `backend/services/aws_account_orchestration.py:169-187`; `backend/services/tenant_reconciliation.py:229-247` | No known implementation gap from repository evidence. | no |
| AWS-023 | S3 GetPublicAccessBlock (Bucket) | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:27; `backend/workers/services/inventory_reconcile.py:143-151`; `backend/services/aws_account_orchestration.py:169-187`; `backend/services/tenant_reconciliation.py:229-247` | No known implementation gap from repository evidence. | no |
| AWS-024 | S3 GetBucketPolicyStatus | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:28; `backend/workers/services/inventory_reconcile.py:166-173`; `backend/services/aws_account_orchestration.py:169-187`; `backend/services/tenant_reconciliation.py:229-247`; `backend/services/remediation_runtime_checks.py:389-399` | No known implementation gap from repository evidence. | no |
| AWS-025 | S3 GetBucketPolicy | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:29; `backend/workers/services/inventory_reconcile.py:265-279`; `backend/services/aws_account_orchestration.py:169-187`; `backend/services/tenant_reconciliation.py:229-247`; `backend/services/remediation_runtime_checks.py:364-378` | No known implementation gap from repository evidence. | no |
| AWS-026 | S3 GetBucketEncryption | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:30; `backend/workers/services/inventory_reconcile.py:176-209`; `backend/services/aws_account_orchestration.py:169-187`; `backend/services/tenant_reconciliation.py:229-247` | No known implementation gap from repository evidence. | no |
| AWS-027 | S3 GetBucketLogging | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:31; `backend/workers/services/inventory_reconcile.py:217-235`; `backend/services/aws_account_orchestration.py:169-187`; `backend/services/tenant_reconciliation.py:229-247` | No known implementation gap from repository evidence. | no |
| AWS-028 | S3 GetBucketLifecycleConfiguration | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:32; `backend/workers/services/inventory_reconcile.py:247-262`; `backend/services/aws_account_orchestration.py:169-187`; `backend/services/tenant_reconciliation.py:229-247` | No known implementation gap from repository evidence. | no |
| AWS-029 | S3 HeadBucket | aws-integration | PARTIAL | docs/features/feat-task5-aws-integration-features.md:33; backend/services/remediation_runtime_checks.py:267-280 | HeadBucket IAM-action mapping remains policy-dependent, so permission-contract behavior is not fully deterministic. | no |
| AWS-030 | S3 PutObject | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:34; `backend/services/evidence_export.py:364-373`; `backend/services/baseline_report_service.py:57-69` | No known implementation gap from repository evidence. | no |
| AWS-031 | S3 ListObjectsV2 | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:35; `backend/services/cloudformation_templates.py:154-213` | No known implementation gap from repository evidence. | no |
| AWS-032 | S3 Control GetPublicAccessBlock (Account) | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:36; `backend/workers/services/inventory_reconcile.py:153-164`; `backend/workers/services/direct_fix.py:175-197;293-320;347-372`; `backend/services/remediation_runtime_checks.py:150-161` | No known implementation gap from repository evidence. | no |
| AWS-033 | S3 Control PutPublicAccessBlock (Account) | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:37; `backend/workers/services/direct_fix.py:325-344` | No known implementation gap from repository evidence. | no |
| AWS-034 | CloudTrail DescribeTrails | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:38; `backend/workers/services/inventory_reconcile.py:646-648`; `backend/services/tenant_reconciliation.py:249-251` | No known implementation gap from repository evidence. | no |
| AWS-035 | CloudTrail GetTrailStatus | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:39; `backend/workers/services/inventory_reconcile.py:659-671` | No known implementation gap from repository evidence. | no |
| AWS-036 | Config DescribeConfigurationRecorders | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:40; `backend/services/aws_account_orchestration.py:317-328`; `backend/workers/services/inventory_reconcile.py:726-729`; `backend/services/tenant_reconciliation.py:251-253` | No known implementation gap from repository evidence. | no |
| AWS-037 | Config DescribeConfigurationRecorderStatus | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:41; `backend/services/aws_account_orchestration.py:318-324`; `backend/workers/services/inventory_reconcile.py:730-738` | No known implementation gap from repository evidence. | no |
| AWS-038 | Config DescribeDeliveryChannels | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:42; `backend/workers/services/inventory_reconcile.py:739-740` | No known implementation gap from repository evidence. | no |
| AWS-039 | IAM GetAccountSummary | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:43; `backend/workers/services/inventory_reconcile.py:859-866` | No known implementation gap from repository evidence. | no |
| AWS-040 | IAM ListAccountAliases | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:44; `backend/services/tenant_reconciliation.py:253-255` | No known implementation gap from repository evidence. | no |
| AWS-041 | RDS DescribeDBInstances | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:45; `backend/workers/services/inventory_reconcile.py:1031-1058`; `backend/services/tenant_reconciliation.py:257-259` | No known implementation gap from repository evidence. | no |
| AWS-042 | EKS ListClusters | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:46; `backend/workers/services/inventory_reconcile.py:1130-1143`; `backend/services/tenant_reconciliation.py:259-261` | No known implementation gap from repository evidence. | no |
| AWS-043 | EKS DescribeCluster | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:47; `backend/workers/services/inventory_reconcile.py:1145-1153` | No known implementation gap from repository evidence. | no |
| AWS-044 | SSM GetServiceSetting | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:48; `backend/workers/services/inventory_reconcile.py:1207-1238` | No known implementation gap from repository evidence. | no |
| AWS-045 | SSM DescribeInstanceInformation | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:49; `backend/services/tenant_reconciliation.py:261-263` | No known implementation gap from repository evidence. | no |
| AWS-046 | GuardDuty ListDetectors | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:50; `backend/workers/services/direct_fix.py:228-239;487-523`; `backend/workers/services/inventory_reconcile.py:1306-1327`; `backend/services/remediation_runtime_checks.py:177-183`; `backend/services/tenant_reconciliation.py:263-265` | No known implementation gap from repository evidence. | no |
| AWS-047 | GuardDuty GetDetector | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:51; `backend/workers/services/direct_fix.py:232-234;493-495;527-531;548-553`; `backend/workers/services/inventory_reconcile.py:1333-1351` | No known implementation gap from repository evidence. | no |
| AWS-048 | GuardDuty CreateDetector | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:52; `backend/workers/services/direct_fix.py:512-539` | No known implementation gap from repository evidence. | no |
| AWS-049 | GuardDuty UpdateDetector | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:53; `backend/workers/services/direct_fix.py:531-534` | No known implementation gap from repository evidence. | no |
| AWS-050 | KMS DescribeKey | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:54; `backend/services/remediation_runtime_checks.py:290-301;329-339` | No known implementation gap from repository evidence. | no |
| AWS-051 | CloudFormation UpdateStack | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:55; `backend/routers/aws_accounts.py:949-1010` | No known implementation gap from repository evidence. | no |
| AWS-052 | CloudFormation DescribeStacks | aws-integration | COMPLETE | docs/features/feat-task5-aws-integration-features.md:56; `backend/routers/aws_accounts.py:1061-1097` | No known implementation gap from repository evidence. | no |
| INF-001 | SQLAlchemy runtime database engines | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:9 | No known implementation gap from repository evidence. | no |
| INF-002 | Alembic migrations + revision guard | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:10 | No known implementation gap from repository evidence. | no |
| INF-003 | DR backup and restore controls | infrastructure | PARTIAL | docs/features/feat-task6-infrastructure-features.md:11 | DR controls are split into a separate stack/runbook and are not integrated into base runtime deploy automation. | yes |
| INF-004 | Serverless build pipeline stack | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:12 | No known implementation gap from repository evidence. | no |
| INF-005 | Runtime deployment automation scripts | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:13 | No known implementation gap from repository evidence. | no |
| INF-006 | CI quality + security gates | infrastructure | PARTIAL | docs/features/feat-task6-infrastructure-features.md:14 | CI gates are present, but no in-repo automatic CD workflow is implemented. | yes |
| INF-007 | Split environment configuration model | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:15 | No known implementation gap from repository evidence. | no |
| INF-008 | Secrets Manager runtime injection | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:16 | No known implementation gap from repository evidence. | no |
| INF-009 | ECS network plane (VPC/ALB/SG/TLS) | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:17 | No known implementation gap from repository evidence. | no |
| INF-010 | Serverless API domain mapping | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:18 | No known implementation gap from repository evidence. | no |
| INF-011 | CDN layer for frontend/API edge caching | infrastructure | MISSING | docs/features/feat-task6-infrastructure-features.md:19 | No CloudFront/CDN implementation is defined in the current infrastructure templates. | no |
| INF-012 | WAF edge protection stack | infrastructure | PARTIAL | docs/features/feat-task6-infrastructure-features.md:20 | WAF stack exists, but attachment is parameter-dependent and not automatically enforced across deployments. | yes |
| INF-013 | Tenant-scoped export object storage | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:21 | No known implementation gap from repository evidence. | no |
| INF-014 | Tenant support-file storage access | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:22 | No known implementation gap from repository evidence. | no |
| INF-015 | Multi-queue SQS + DLQ + quarantine topology | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:23 | No known implementation gap from repository evidence. | no |
| INF-016 | Worker trigger and job dispatch fabric | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:24 | No known implementation gap from repository evidence. | no |
| INF-017 | CloudWatch runtime log infrastructure | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:25 | No known implementation gap from repository evidence. | no |
| INF-018 | Metrics collection and readiness SLO snapshots | infrastructure | PARTIAL | docs/features/feat-task6-infrastructure-features.md:26 | Core readiness metrics exist, but dashboarding and extended metric coverage remain manual. | yes |
| INF-019 | Alarming and notification hooks | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:27 | No known implementation gap from repository evidence. | no |
| INF-020 | Health and readiness endpoints | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:28 | No known implementation gap from repository evidence. | no |
| INF-021 | JWT/cookie/CSRF authentication substrate | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:29 | No known implementation gap from repository evidence. | no |
| INF-022 | Tenant isolation substrate | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:30 | No known implementation gap from repository evidence. | no |
| INF-023 | Transactional + digest email delivery | infrastructure | PARTIAL | docs/features/feat-task6-infrastructure-features.md:31 | SMTP-backed email works, but SES-native production delivery is not implemented. | no |
| INF-024 | Scheduler and cron ingress | infrastructure | COMPLETE | docs/features/feat-task6-infrastructure-features.md:32 | No known implementation gap from repository evidence. | no |

STATUS SUMMARY BY CATEGORY
| Category | Complete | Partial | Stub | Missing | Broken | Total |
|---------|---------|---------|------|---------|--------|-------|
| frontend | 80 | 2 | 2 | 8 | 0 | 92 |
| api | 114 | 1 | 0 | 0 | 0 | 115 |
| job | 17 | 1 | 0 | 0 | 0 | 18 |
| aws-integration | 51 | 1 | 0 | 0 | 0 | 52 |
| infrastructure | 18 | 5 | 0 | 1 | 0 | 24 |

GA BLOCKERS LIST

Category: frontend
- FE-007 Forgot password request: Password-reset request API route is not implemented, so the flow cannot start.
- FE-010 Reset password: Password-reset completion API route is not implemented, so reset tokens cannot be applied.
- FE-048 Manual workflow evidence upload: Manual-workflow evidence and validation routes are not implemented, so required evidence handling cannot run.
- FE-062 Audit log explorer: Audit-log API route is not implemented, so admin audit-log queries cannot be served.
- FE-073 Settings password management: Password-change and forgot-password API routes are not implemented, so settings password management is non-functional.

Category: api
- None.

Category: job
- None.

Category: aws-integration
- None.

Category: infrastructure
- INF-003 DR backup and restore controls: DR controls are split into a separate stack/runbook and are not integrated into base runtime deploy automation.
- INF-006 CI quality + security gates: CI gates are present, but no in-repo automatic CD workflow is implemented.
- INF-012 WAF edge protection stack: WAF stack exists, but attachment is parameter-dependent and not automatically enforced across deployments.
- INF-018 Metrics collection and readiness SLO snapshots: Core readiness metrics exist, but dashboarding and extended metric coverage remain manual.

QUICK WINS
| Feature ID | Feature Name | What is missing | Estimated fix effort |
|-----------|-------------|-----------------|---------------------|
| FE-002 | Marketing site nav + hero CTAs | Contains TODO placeholders for some marketing assets/links. | <0.25 day |
| AWS-029 | S3 HeadBucket | HeadBucket IAM-action mapping remains policy-dependent, so permission-contract behavior is not fully deterministic. | <0.25 day |
