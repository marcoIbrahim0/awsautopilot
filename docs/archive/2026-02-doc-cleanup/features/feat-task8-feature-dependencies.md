FEATURE DEPENDENCY MAP

> Historical note (2026-03-15): Public SaaS-managed PR-bundle plan/apply is archived. Customer-run PR bundles remain supported; the dependency map below reflects the February 2026 snapshot, not the current product direction.

> ⚠️ Input gap: `docs/prod-readiness/05-e2e-test-scenarios.md` is not present in this repository. The 8 required journeys below are inferred from `feat-task2`-`feat-task5`.

| Feature ID | Feature Name | Depends on Feature ID | Dependency type | What breaks if dependency is unavailable |
|---|---|---|---|---|
| FE-006 | Login | API-012 | hard | POST /api/auth/login cannot complete from the UI; the user flow fails at request execution. |
| FE-008 | Signup | API-011 | hard | POST /api/auth/signup cannot complete from the UI; the user flow fails at request execution. |
| FE-009 | Accept invite | API-109 | hard | POST /api/users/accept-invite cannot complete from the UI; the user flow fails at request execution. |
| FE-017 | Accounts list + sectional views | API-017 | hard | GET /api/aws/accounts cannot complete from the UI; the user flow fails at request execution. |
| FE-018 | Connect/reconnect AWS account | API-022 | hard | POST /api/aws/accounts cannot complete from the UI; the user flow fails at request execution. |
| FE-020 | Validate account role | API-023 | hard | POST /api/aws/accounts/{account_id}/validate cannot complete from the UI; the user flow fails at request execution. |
| FE-021 | Stop/resume monitoring | API-018 | hard | PATCH /api/aws/accounts/{account_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-022 | Remove account | API-019 | hard | DELETE /api/aws/accounts/{account_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-023 | Ingest refresh by source | API-027 | hard | POST /api/aws/accounts/{account_id}/ingest cannot complete from the UI; the user flow fails at request execution. |
| FE-023 | Ingest refresh by source | API-029 | hard | POST /api/aws/accounts/{account_id}/ingest-access-analyzer cannot complete from the UI; the user flow fails at request execution. |
| FE-023 | Ingest refresh by source | API-030 | hard | POST /api/aws/accounts/{account_id}/ingest-inspector cannot complete from the UI; the user flow fails at request execution. |
| FE-025 | Ingest progress polling | API-028 | hard | GET /api/aws/accounts/{account_id}/ingest-progress cannot complete from the UI; the user flow fails at request execution. |
| FE-026 | Reconciliation preflight/run | API-061 | hard | POST /api/reconciliation/preflight cannot complete from the UI; the user flow fails at request execution. |
| FE-026 | Reconciliation preflight/run | API-062 | hard | POST /api/reconciliation/run cannot complete from the UI; the user flow fails at request execution. |
| FE-027 | Reconciliation schedule management | API-065 | hard | GET /api/reconciliation/settings/{account_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-027 | Reconciliation schedule management | API-066 | hard | PUT /api/reconciliation/settings/{account_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-027 | Reconciliation schedule management | API-063 | hard | GET /api/reconciliation/status cannot complete from the UI; the user flow fails at request execution. |
| FE-027 | Reconciliation schedule management | API-064 | hard | GET /api/reconciliation/coverage cannot complete from the UI; the user flow fails at request execution. |
| FE-030 | Launch-stack role setup links | API-014 | hard | GET /api/auth/me cannot complete from the UI; the user flow fails at request execution. |
| FE-031 | Validate integration role | API-022 | hard | POST /api/aws/accounts cannot complete from the UI; the user flow fails at request execution. |
| FE-033 | Control-plane readiness check | API-026 | hard | GET /api/aws/accounts/{account_id}/control-plane-readiness cannot complete from the UI; the user flow fails at request execution. |
| FE-034 | Control-plane token rotate/revoke | API-015 | hard | POST /api/auth/control-plane-token/rotate cannot complete from the UI; the user flow fails at request execution. |
| FE-034 | Control-plane token rotate/revoke | API-016 | hard | POST /api/auth/control-plane-token/revoke cannot complete from the UI; the user flow fails at request execution. |
| FE-035 | Fast-path onboarding trigger | API-025 | hard | POST /api/aws/accounts/{account_id}/onboarding-fast-path cannot complete from the UI; the user flow fails at request execution. |
| FE-036 | Final checks + queue initial workload | API-026 | hard | GET /api/aws/accounts/{account_id}/control-plane-readiness cannot complete from the UI; the user flow fails at request execution. |
| FE-036 | Final checks + queue initial workload | API-027 | hard | POST /api/aws/accounts/{account_id}/ingest cannot complete from the UI; the user flow fails at request execution. |
| FE-036 | Final checks + queue initial workload | API-010 | hard | POST /api/actions/compute cannot complete from the UI; the user flow fails at request execution. |
| FE-036 | Final checks + queue initial workload | API-110 | hard | PATCH /api/users/me cannot complete from the UI; the user flow fails at request execution. |
| FE-037 | Findings filters and source/severity tabs | API-048 | hard | GET /api/findings cannot complete from the UI; the user flow fails at request execution. |
| FE-037 | Findings filters and source/severity tabs | API-060 | hard | GET /api/meta/scope cannot complete from the UI; the user flow fails at request execution. |
| FE-037 | Findings filters and source/severity tabs | API-017 | hard | GET /api/aws/accounts cannot complete from the UI; the user flow fails at request execution. |
| FE-038 | Grouped findings mode | API-047 | hard | GET /api/findings/grouped cannot complete from the UI; the user flow fails at request execution. |
| FE-041 | First-run processing tracker | API-048 | hard | GET /api/findings cannot complete from the UI; the user flow fails at request execution. |
| FE-041 | First-run processing tracker | API-005 | hard | GET /api/actions cannot complete from the UI; the user flow fails at request execution. |
| FE-042 | Retry first-run processing | API-027 | hard | POST /api/aws/accounts/{account_id}/ingest cannot complete from the UI; the user flow fails at request execution. |
| FE-042 | Retry first-run processing | API-010 | hard | POST /api/actions/compute cannot complete from the UI; the user flow fails at request execution. |
| FE-043 | Findings pagination | API-048 | hard | GET /api/findings cannot complete from the UI; the user flow fails at request execution. |
| FE-043 | Findings pagination | API-047 | hard | GET /api/findings/grouped cannot complete from the UI; the user flow fails at request execution. |
| FE-044 | Finding detail page | API-049 | hard | GET /api/findings/{id} cannot complete from the UI; the user flow fails at request execution. |
| FE-045 | Action detail drawer | API-006 | hard | GET /api/actions/{id} cannot complete from the UI; the user flow fails at request execution. |
| FE-045 | Action detail drawer | API-017 | hard | GET /api/aws/accounts cannot complete from the UI; the user flow fails at request execution. |
| FE-045 | Action detail drawer | API-069 | hard | GET /api/remediation-runs cannot complete from the UI; the user flow fails at request execution. |
| FE-045 | Action detail drawer | API-007 | hard | GET /api/actions/{id}/remediation-options cannot complete from the UI; the user flow fails at request execution. |
| FE-046 | Recompute actions from drawer | API-010 | hard | POST /api/actions/compute cannot complete from the UI; the user flow fails at request execution. |
| FE-046 | Recompute actions from drawer | API-006 | hard | GET /api/actions/{id} cannot complete from the UI; the user flow fails at request execution. |
| FE-047 | Remediation strategy selection | API-007 | hard | GET /api/actions/{action_id}/remediation-options cannot complete from the UI; the user flow fails at request execution. |
| FE-047 | Remediation strategy selection | API-008 | hard | GET /api/actions/{action_id}/remediation-preview cannot complete from the UI; the user flow fails at request execution. |
| FE-049 | Create remediation run | API-067 | hard | POST /api/remediation-runs cannot complete from the UI; the user flow fails at request execution. |
| FE-049 | Create remediation run | API-069 | hard | GET /api/remediation-runs cannot complete from the UI; the user flow fails at request execution. |
| FE-050 | Create exception modal | API-040 | hard | POST /api/exceptions cannot complete from the UI; the user flow fails at request execution. |
| FE-051 | Action-group persistent view | API-001 | hard | GET /api/action-groups cannot complete from the UI; the user flow fails at request execution. |
| FE-051 | Action-group persistent view | API-002 | hard | GET /api/action-groups/{group_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-051 | Action-group persistent view | API-003 | hard | GET /api/action-groups/{group_id}/runs cannot complete from the UI; the user flow fails at request execution. |
| FE-052 | Action-group bundle run generation | API-004 | hard | POST /api/action-groups/{group_id}/bundle-run cannot complete from the UI; the user flow fails at request execution. |
| FE-053 | Action-group bundle download | API-071 | hard | GET /api/remediation-runs/{run_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-054 | Top-risks dashboard | API-048 | hard | GET /api/findings cannot complete from the UI; the user flow fails at request execution. |
| FE-055 | Exceptions list and filtering | API-041 | hard | GET /api/exceptions cannot complete from the UI; the user flow fails at request execution. |
| FE-056 | Revoke exception | API-043 | hard | DELETE /api/exceptions/{exception_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-057 | Evidence/compliance export creation | API-044 | hard | POST /api/exports cannot complete from the UI; the user flow fails at request execution. |
| FE-057 | Evidence/compliance export creation | API-046 | hard | GET /api/exports/{export_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-058 | Export history and ad-hoc download | API-045 | hard | GET /api/exports cannot complete from the UI; the user flow fails at request execution. |
| FE-058 | Export history and ad-hoc download | API-046 | hard | GET /api/exports/{export_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-059 | Baseline report request from exports tab | API-033 | hard | POST /api/baseline-report cannot complete from the UI; the user flow fails at request execution. |
| FE-059 | Baseline report request from exports tab | API-035 | hard | GET /api/baseline-report/{report_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-059 | Baseline report request from exports tab | API-034 | hard | GET /api/baseline-report cannot complete from the UI; the user flow fails at request execution. |
| FE-060 | Baseline report viewer page | API-033 | hard | POST /api/baseline-report cannot complete from the UI; the user flow fails at request execution. |
| FE-060 | Baseline report viewer page | API-035 | hard | GET /api/baseline-report/{report_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-060 | Baseline report viewer page | API-034 | hard | GET /api/baseline-report cannot complete from the UI; the user flow fails at request execution. |
| FE-061 | Support files download center | API-104 | hard | GET /api/support-files cannot complete from the UI; the user flow fails at request execution. |
| FE-061 | Support files download center | API-105 | hard | GET /api/support-files/{file_id}/download cannot complete from the UI; the user flow fails at request execution. |
| FE-063 | PR bundle history | API-069 | hard | GET /api/remediation-runs cannot complete from the UI; the user flow fails at request execution. |
| FE-064 | PR bundle action picker | API-005 | hard | GET /api/actions cannot complete from the UI; the user flow fails at request execution. |
| FE-065 | PR bundle summary generation | API-005 | hard | GET /api/actions cannot complete from the UI; the user flow fails at request execution. |
| FE-065 | PR bundle summary generation | API-067 | hard | POST /api/remediation-runs cannot complete from the UI; the user flow fails at request execution. |
| FE-065 | PR bundle summary generation | API-068 | hard | POST /api/remediation-runs/group-pr-bundle cannot complete from the UI; the user flow fails at request execution. |
| FE-066 | Online execution controls for generated bundles | API-072 | hard | POST /api/remediation-runs/bulk-execute-pr-bundle cannot complete from the UI; the user flow fails at request execution. |
| FE-066 | Online execution controls for generated bundles | API-073 | hard | POST /api/remediation-runs/bulk-approve-apply cannot complete from the UI; the user flow fails at request execution. |
| FE-066 | Online execution controls for generated bundles | API-076 | hard | GET /api/remediation-runs/{run_id}/execution cannot complete from the UI; the user flow fails at request execution. |
| FE-067 | Remediation run live status | API-071 | hard | GET /api/remediation-runs/{run_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-069 | Resend stale remediation run | API-077 | hard | POST /api/remediation-runs/{run_id}/resend cannot complete from the UI; the user flow fails at request execution. |
| FE-070 | Download generated PR files from run | API-071 | hard | GET /api/remediation-runs/{run_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-071 | Settings profile update | API-110 | hard | PATCH /api/users/me cannot complete from the UI; the user flow fails at request execution. |
| FE-075 | Team invite | API-107 | hard | POST /api/users/invite cannot complete from the UI; the user flow fails at request execution. |
| FE-075 | Team invite | API-106 | hard | GET /api/users cannot complete from the UI; the user flow fails at request execution. |
| FE-076 | Team member removal | API-115 | hard | DELETE /api/users/{user_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-076 | Team member removal | API-106 | hard | GET /api/users cannot complete from the UI; the user flow fails at request execution. |
| FE-077 | Digest notification settings | API-111 | hard | GET /api/users/me/digest-settings cannot complete from the UI; the user flow fails at request execution. |
| FE-077 | Digest notification settings | API-112 | hard | PATCH /api/users/me/digest-settings cannot complete from the UI; the user flow fails at request execution. |
| FE-078 | Slack notification settings | API-113 | hard | GET /api/users/me/slack-settings cannot complete from the UI; the user flow fails at request execution. |
| FE-078 | Slack notification settings | API-114 | hard | PATCH /api/users/me/slack-settings cannot complete from the UI; the user flow fails at request execution. |
| FE-079 | Settings evidence export panel | API-044 | hard | POST /api/exports cannot complete from the UI; the user flow fails at request execution. |
| FE-079 | Settings evidence export panel | API-045 | hard | GET /api/exports cannot complete from the UI; the user flow fails at request execution. |
| FE-079 | Settings evidence export panel | API-046 | hard | GET /api/exports/{export_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-080 | Control mappings management | API-036 | hard | GET /api/control-mappings cannot complete from the UI; the user flow fails at request execution. |
| FE-080 | Control mappings management | API-038 | hard | POST /api/control-mappings cannot complete from the UI; the user flow fails at request execution. |
| FE-081 | Settings baseline report panel | API-033 | hard | POST /api/baseline-report cannot complete from the UI; the user flow fails at request execution. |
| FE-081 | Settings baseline report panel | API-034 | hard | GET /api/baseline-report cannot complete from the UI; the user flow fails at request execution. |
| FE-081 | Settings baseline report panel | API-035 | hard | GET /api/baseline-report/{report_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-082 | Organization readiness + launch workflow | API-017 | hard | GET /api/aws/accounts cannot complete from the UI; the user flow fails at request execution. |
| FE-082 | Organization readiness + launch workflow | API-026 | hard | GET /api/aws/accounts/{account_id}/control-plane-readiness cannot complete from the UI; the user flow fails at request execution. |
| FE-083 | SaaS admin tenant list | API-089 | hard | GET /api/saas/tenants cannot complete from the UI; the user flow fails at request execution. |
| FE-083 | SaaS admin tenant list | API-079 | hard | GET /api/saas/system-health cannot complete from the UI; the user flow fails at request execution. |
| FE-084 | SaaS admin tenant detail workspace | API-090 | hard | GET /api/saas/tenants/{tenant_id} cannot complete from the UI; the user flow fails at request execution. |
| FE-085 | Admin support note creation | API-099 | hard | POST /api/saas/tenants/{tenant_id}/notes cannot complete from the UI; the user flow fails at request execution. |
| FE-086 | Admin support file upload | API-101 | hard | POST /api/saas/tenants/{tenant_id}/files/initiate cannot complete from the UI; the user flow fails at request execution. |
| FE-086 | Admin support file upload | API-102 | hard | POST /api/saas/tenants/{tenant_id}/files/{file_id}/finalize cannot complete from the UI; the user flow fails at request execution. |
| FE-087 | Control-plane global ops dashboard | API-080 | hard | GET /api/saas/control-plane/slo cannot complete from the UI; the user flow fails at request execution. |
| FE-087 | Control-plane global ops dashboard | API-089 | hard | GET /api/saas/tenants cannot complete from the UI; the user flow fails at request execution. |
| FE-088 | Control-plane tenant drilldown | API-080 | hard | GET /api/saas/control-plane/slo cannot complete from the UI; the user flow fails at request execution. |
| FE-088 | Control-plane tenant drilldown | API-081 | hard | GET /api/saas/control-plane/shadow-summary cannot complete from the UI; the user flow fails at request execution. |
| FE-088 | Control-plane tenant drilldown | API-083 | hard | GET /api/saas/control-plane/compare cannot complete from the UI; the user flow fails at request execution. |
| FE-088 | Control-plane tenant drilldown | API-082 | hard | GET /api/saas/control-plane/shadow-compare cannot complete from the UI; the user flow fails at request execution. |
| FE-089 | Control-plane reconcile enqueue actions | API-086 | hard | POST /api/saas/control-plane/reconcile/recently-touched cannot complete from the UI; the user flow fails at request execution. |
| FE-089 | Control-plane reconcile enqueue actions | API-087 | hard | POST /api/saas/control-plane/reconcile/global cannot complete from the UI; the user flow fails at request execution. |
| FE-089 | Control-plane reconcile enqueue actions | API-088 | hard | POST /api/saas/control-plane/reconcile/shard cannot complete from the UI; the user flow fails at request execution. |
| FE-090 | Control-plane reconcile job history | API-085 | hard | GET /api/saas/control-plane/reconcile-jobs cannot complete from the UI; the user flow fails at request execution. |
| FE-007 | Forgot password request | API-MISSING-001 | hard | Frontend calls POST /api/auth/forgot-password, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-010 | Reset password | API-MISSING-002 | hard | Frontend calls POST /api/auth/reset-password, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-032 | Service readiness checks | API-MISSING-003 | hard | Frontend calls GET /api/aws/accounts/{account_id}/service-readiness, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-036 | Final checks + queue initial workload | API-MISSING-004 | hard | Frontend calls GET /api/aws/accounts/{account_id}/service-readiness, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-039 | Group-level actions on findings | API-MISSING-005 | hard | Frontend calls POST /api/findings/group-actions, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-048 | Manual workflow evidence upload | API-MISSING-006 | hard | Frontend calls GET /api/actions/{action_id}/manual-workflow/evidence, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-048 | Manual workflow evidence upload | API-MISSING-007 | hard | Frontend calls POST /api/actions/{action_id}/manual-workflow/evidence/upload, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-060 | Baseline report viewer page | API-MISSING-008 | hard | Frontend calls GET /api/baseline-report/{report_id}/data, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-062 | Audit log explorer | API-MISSING-009 | hard | Frontend calls GET /api/audit-log, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-068 | Cancel remediation run | API-MISSING-010 | hard | Frontend calls DELETE /api/remediation-runs/{run_id}, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-072 | Email/phone verification modal | API-MISSING-011 | hard | Frontend calls POST /api/auth/verify/send, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-072 | Email/phone verification modal | API-MISSING-012 | hard | Frontend calls POST /api/auth/verify/confirm, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-073 | Settings password management | API-MISSING-013 | hard | Frontend calls PUT /api/auth/password, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-073 | Settings password management | API-MISSING-014 | hard | Frontend calls POST /api/auth/forgot-password, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-074 | Settings account deletion | API-MISSING-015 | hard | Frontend calls DELETE /api/users/me, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| FE-082 | Organization readiness + launch workflow | API-MISSING-016 | hard | Frontend calls GET /api/aws/accounts/{account_id}/service-readiness, but no matching API feature exists in Task 3 inventory; flow fails or is undocumented. |
| API-010 | POST /api/actions/compute | JOB-007 | sequential | Async side effects do not occur; request may return but downstream processing remains incomplete. |
| API-025 | POST /api/aws/accounts/{account_id}/onboarding-fast-path | JOB-003 | sequential | Async side effects do not occur; request may return but downstream processing remains incomplete. |
| API-025 | POST /api/aws/accounts/{account_id}/onboarding-fast-path | JOB-007 | sequential | Async side effects do not occur; request may return but downstream processing remains incomplete. |
| API-033 | POST /api/baseline-report | JOB-015 | sequential | Async side effects do not occur; request may return but downstream processing remains incomplete. |
| API-039 | POST /api/control-plane/events | JOB-006 | sequential | Async side effects do not occur; request may return but downstream processing remains incomplete. |
| API-044 | POST /api/exports | JOB-014 | sequential | Async side effects do not occur; request may return but downstream processing remains incomplete. |
| API-050 | POST /api/internal/weekly-digest | JOB-016 | sequential | Async side effects do not occur; request may return but downstream processing remains incomplete. |
| API-051 | POST /api/internal/control-plane-events | JOB-006 | sequential | Async side effects do not occur; request may return but downstream processing remains incomplete. |
| API-052 | POST /api/internal/reconcile-inventory-shard | JOB-009 | sequential | Async side effects do not occur; request may return but downstream processing remains incomplete. |
| API-077 | POST /api/remediation-runs/{run_id}/resend | JOB-011 | sequential | Async side effects do not occur; request may return but downstream processing remains incomplete. |
| API-088 | POST /api/saas/control-plane/reconcile/shard | JOB-009 | sequential | Async side effects do not occur; request may return but downstream processing remains incomplete. |
| API-017 | GET /api/aws/accounts | AWS-001 | hard | Direct AWS dependency (STS AssumeRole) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-001 | hard | Direct AWS dependency (STS AssumeRole) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-001 | hard | Direct AWS dependency (STS AssumeRole) is unavailable; endpoint returns degraded/error behavior. |
| API-067 | POST /api/remediation-runs | AWS-001 | hard | Direct AWS dependency (STS AssumeRole) is unavailable; endpoint returns degraded/error behavior. |
| API-069 | GET /api/remediation-runs | AWS-001 | hard | Direct AWS dependency (STS AssumeRole) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-002 | hard | Direct AWS dependency (STS GetCallerIdentity) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-002 | hard | Direct AWS dependency (STS GetCallerIdentity) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-003 | hard | Direct AWS dependency (SQS SendMessage) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-003 | hard | Direct AWS dependency (SQS SendMessage) is unavailable; endpoint returns degraded/error behavior. |
| API-039 | POST /api/control-plane/events | AWS-003 | hard | Direct AWS dependency (SQS SendMessage) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-005 | hard | Direct AWS dependency (Security Hub GetFindings) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-005 | hard | Direct AWS dependency (Security Hub GetFindings) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-006 | hard | Direct AWS dependency (Security Hub DescribeHub) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-006 | hard | Direct AWS dependency (Security Hub DescribeHub) is unavailable; endpoint returns degraded/error behavior. |
| API-067 | POST /api/remediation-runs | AWS-007 | hard | Direct AWS dependency (Security Hub GetEnabledStandards) is unavailable; endpoint returns degraded/error behavior. |
| API-069 | GET /api/remediation-runs | AWS-007 | hard | Direct AWS dependency (Security Hub GetEnabledStandards) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-009 | hard | Direct AWS dependency (IAM Access Analyzer ListAnalyzers) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-009 | hard | Direct AWS dependency (IAM Access Analyzer ListAnalyzers) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-012 | hard | Direct AWS dependency (Inspector2 BatchGetAccountStatus) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-012 | hard | Direct AWS dependency (Inspector2 BatchGetAccountStatus) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-013 | hard | Direct AWS dependency (EC2 DescribeSecurityGroups) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-013 | hard | Direct AWS dependency (EC2 DescribeSecurityGroups) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-013 | hard | Direct AWS dependency (EC2 DescribeSecurityGroups) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-014 | hard | Direct AWS dependency (EC2 DescribeVolumes) is unavailable; endpoint returns degraded/error behavior. |
| API-062 | POST /api/reconciliation/run | AWS-014 | hard | Direct AWS dependency (EC2 DescribeVolumes) is unavailable; endpoint returns degraded/error behavior. |
| API-067 | POST /api/remediation-runs | AWS-015 | hard | Direct AWS dependency (EC2 DescribeSnapshots) is unavailable; endpoint returns degraded/error behavior. |
| API-069 | GET /api/remediation-runs | AWS-015 | hard | Direct AWS dependency (EC2 DescribeSnapshots) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-021 | hard | Direct AWS dependency (S3 ListBuckets) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-021 | hard | Direct AWS dependency (S3 ListBuckets) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-021 | hard | Direct AWS dependency (S3 ListBuckets) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-022 | hard | Direct AWS dependency (S3 GetBucketLocation) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-022 | hard | Direct AWS dependency (S3 GetBucketLocation) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-022 | hard | Direct AWS dependency (S3 GetBucketLocation) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-023 | hard | Direct AWS dependency (S3 GetPublicAccessBlock (Bucket)) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-023 | hard | Direct AWS dependency (S3 GetPublicAccessBlock (Bucket)) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-023 | hard | Direct AWS dependency (S3 GetPublicAccessBlock (Bucket)) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-024 | hard | Direct AWS dependency (S3 GetBucketPolicyStatus) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-024 | hard | Direct AWS dependency (S3 GetBucketPolicyStatus) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-024 | hard | Direct AWS dependency (S3 GetBucketPolicyStatus) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-025 | hard | Direct AWS dependency (S3 GetBucketPolicy) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-025 | hard | Direct AWS dependency (S3 GetBucketPolicy) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-025 | hard | Direct AWS dependency (S3 GetBucketPolicy) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-026 | hard | Direct AWS dependency (S3 GetBucketEncryption) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-026 | hard | Direct AWS dependency (S3 GetBucketEncryption) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-026 | hard | Direct AWS dependency (S3 GetBucketEncryption) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-027 | hard | Direct AWS dependency (S3 GetBucketLogging) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-027 | hard | Direct AWS dependency (S3 GetBucketLogging) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-027 | hard | Direct AWS dependency (S3 GetBucketLogging) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-028 | hard | Direct AWS dependency (S3 GetBucketLifecycleConfiguration) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-028 | hard | Direct AWS dependency (S3 GetBucketLifecycleConfiguration) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-028 | hard | Direct AWS dependency (S3 GetBucketLifecycleConfiguration) is unavailable; endpoint returns degraded/error behavior. |
| API-067 | POST /api/remediation-runs | AWS-029 | hard | Direct AWS dependency (S3 HeadBucket) is unavailable; endpoint returns degraded/error behavior. |
| API-069 | GET /api/remediation-runs | AWS-029 | hard | Direct AWS dependency (S3 HeadBucket) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-031 | hard | Direct AWS dependency (S3 ListObjectsV2) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-031 | hard | Direct AWS dependency (S3 ListObjectsV2) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-034 | hard | Direct AWS dependency (CloudTrail DescribeTrails) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-036 | hard | Direct AWS dependency (Config DescribeConfigurationRecorders) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-036 | hard | Direct AWS dependency (Config DescribeConfigurationRecorders) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-036 | hard | Direct AWS dependency (Config DescribeConfigurationRecorders) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-037 | hard | Direct AWS dependency (Config DescribeConfigurationRecorderStatus) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-037 | hard | Direct AWS dependency (Config DescribeConfigurationRecorderStatus) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-040 | hard | Direct AWS dependency (IAM ListAccountAliases) is unavailable; endpoint returns degraded/error behavior. |
| API-062 | POST /api/reconciliation/run | AWS-040 | hard | Direct AWS dependency (IAM ListAccountAliases) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-041 | hard | Direct AWS dependency (RDS DescribeDBInstances) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-042 | hard | Direct AWS dependency (EKS ListClusters) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-045 | hard | Direct AWS dependency (SSM DescribeInstanceInformation) is unavailable; endpoint returns degraded/error behavior. |
| API-062 | POST /api/reconciliation/run | AWS-045 | hard | Direct AWS dependency (SSM DescribeInstanceInformation) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-046 | hard | Direct AWS dependency (GuardDuty ListDetectors) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-046 | hard | Direct AWS dependency (GuardDuty ListDetectors) is unavailable; endpoint returns degraded/error behavior. |
| API-061 | POST /api/reconciliation/preflight | AWS-046 | hard | Direct AWS dependency (GuardDuty ListDetectors) is unavailable; endpoint returns degraded/error behavior. |
| API-067 | POST /api/remediation-runs | AWS-046 | hard | Direct AWS dependency (GuardDuty ListDetectors) is unavailable; endpoint returns degraded/error behavior. |
| API-069 | GET /api/remediation-runs | AWS-046 | hard | Direct AWS dependency (GuardDuty ListDetectors) is unavailable; endpoint returns degraded/error behavior. |
| API-067 | POST /api/remediation-runs | AWS-050 | hard | Direct AWS dependency (KMS DescribeKey) is unavailable; endpoint returns degraded/error behavior. |
| API-069 | GET /api/remediation-runs | AWS-050 | hard | Direct AWS dependency (KMS DescribeKey) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-051 | hard | Direct AWS dependency (CloudFormation UpdateStack) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-051 | hard | Direct AWS dependency (CloudFormation UpdateStack) is unavailable; endpoint returns degraded/error behavior. |
| API-017 | GET /api/aws/accounts | AWS-052 | hard | Direct AWS dependency (CloudFormation DescribeStacks) is unavailable; endpoint returns degraded/error behavior. |
| API-022 | POST /api/aws/accounts | AWS-052 | hard | Direct AWS dependency (CloudFormation DescribeStacks) is unavailable; endpoint returns degraded/error behavior. |
| JOB-003 | ingest_findings | AWS-005 | data | Worker execution cannot read/write required AWS state (Security Hub GetFindings); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-006 | data | Worker execution cannot read/write required AWS state (Security Hub DescribeHub); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-007 | data | Worker execution cannot read/write required AWS state (Security Hub GetEnabledStandards); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-008 | data | Worker execution cannot read/write required AWS state (Security Hub EnableSecurityHub); job retries/fails or records degraded outcome. |
| JOB-004 | ingest_access_analyzer | AWS-009 | data | Worker execution cannot read/write required AWS state (IAM Access Analyzer ListAnalyzers); job retries/fails or records degraded outcome. |
| JOB-004 | ingest_access_analyzer | AWS-010 | data | Worker execution cannot read/write required AWS state (IAM Access Analyzer ListFindings); job retries/fails or records degraded outcome. |
| JOB-005 | ingest_inspector | AWS-011 | data | Worker execution cannot read/write required AWS state (Inspector2 ListFindings); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-013 | data | Worker execution cannot read/write required AWS state (EC2 DescribeSecurityGroups); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-016 | data | Worker execution cannot read/write required AWS state (EC2 GetEbsEncryptionByDefault); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-016 | data | Worker execution cannot read/write required AWS state (EC2 GetEbsEncryptionByDefault); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-017 | data | Worker execution cannot read/write required AWS state (EC2 GetEbsDefaultKmsKeyId); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-018 | data | Worker execution cannot read/write required AWS state (EC2 EnableEbsEncryptionByDefault); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-019 | data | Worker execution cannot read/write required AWS state (EC2 ModifyEbsDefaultKmsKeyId); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-020 | data | Worker execution cannot read/write required AWS state (EC2 GetSnapshotBlockPublicAccessState); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-021 | data | Worker execution cannot read/write required AWS state (S3 ListBuckets); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-022 | data | Worker execution cannot read/write required AWS state (S3 GetBucketLocation); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-023 | data | Worker execution cannot read/write required AWS state (S3 GetPublicAccessBlock (Bucket)); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-024 | data | Worker execution cannot read/write required AWS state (S3 GetBucketPolicyStatus); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-025 | data | Worker execution cannot read/write required AWS state (S3 GetBucketPolicy); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-026 | data | Worker execution cannot read/write required AWS state (S3 GetBucketEncryption); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-027 | data | Worker execution cannot read/write required AWS state (S3 GetBucketLogging); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-028 | data | Worker execution cannot read/write required AWS state (S3 GetBucketLifecycleConfiguration); job retries/fails or records degraded outcome. |
| JOB-014 | generate_export | AWS-030 | data | Worker execution cannot read/write required AWS state (S3 PutObject); job retries/fails or records degraded outcome. |
| JOB-015 | generate_baseline_report | AWS-030 | data | Worker execution cannot read/write required AWS state (S3 PutObject); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-032 | data | Worker execution cannot read/write required AWS state (S3 Control GetPublicAccessBlock (Account)); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-032 | data | Worker execution cannot read/write required AWS state (S3 Control GetPublicAccessBlock (Account)); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-033 | data | Worker execution cannot read/write required AWS state (S3 Control PutPublicAccessBlock (Account)); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-034 | data | Worker execution cannot read/write required AWS state (CloudTrail DescribeTrails); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-035 | data | Worker execution cannot read/write required AWS state (CloudTrail GetTrailStatus); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-036 | data | Worker execution cannot read/write required AWS state (Config DescribeConfigurationRecorders); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-037 | data | Worker execution cannot read/write required AWS state (Config DescribeConfigurationRecorderStatus); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-038 | data | Worker execution cannot read/write required AWS state (Config DescribeDeliveryChannels); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-039 | data | Worker execution cannot read/write required AWS state (IAM GetAccountSummary); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-041 | data | Worker execution cannot read/write required AWS state (RDS DescribeDBInstances); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-042 | data | Worker execution cannot read/write required AWS state (EKS ListClusters); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-043 | data | Worker execution cannot read/write required AWS state (EKS DescribeCluster); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-044 | data | Worker execution cannot read/write required AWS state (SSM GetServiceSetting); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-046 | data | Worker execution cannot read/write required AWS state (GuardDuty ListDetectors); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-046 | data | Worker execution cannot read/write required AWS state (GuardDuty ListDetectors); job retries/fails or records degraded outcome. |
| JOB-009 | reconcile_inventory_shard | AWS-047 | data | Worker execution cannot read/write required AWS state (GuardDuty GetDetector); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-047 | data | Worker execution cannot read/write required AWS state (GuardDuty GetDetector); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-048 | data | Worker execution cannot read/write required AWS state (GuardDuty CreateDetector); job retries/fails or records degraded outcome. |
| JOB-011 | remediation_run | AWS-049 | data | Worker execution cannot read/write required AWS state (GuardDuty UpdateDetector); job retries/fails or records degraded outcome. |

USER JOURNEY MAP

JOURNEY: J1 Inferred — New Signup to First Findings Visibility
Step 1 → FE-008 (Signup) → API-011 (POST /api/auth/signup)
Step 2 → FE-031 (Validate integration role) → API-022 (POST /api/aws/accounts) → AWS-001 (STS:AssumeRole)
Step 3 → FE-036 (Final checks + queue initial workload) → API-027 (POST /api/aws/accounts/{account_id}/ingest) → JOB-003 (ingest_findings) → AWS-005 (Security Hub:GetFindings)
Step 4 → FE-036 (Final checks + queue initial workload) → API-010 (POST /api/actions/compute) → JOB-007 (compute_actions)
Step 5 → FE-037 (Findings filters and source/severity tabs) → API-048 (GET /api/findings)
Final state: User lands on Findings and sees ingested findings and computed actions.
Failure points: FE-031, API-022, API-027, JOB-003, AWS-005, API-010, or JOB-007.

JOURNEY: J2 Inferred — Login and Findings Triage
Step 1 → FE-006 (Login) → API-012 (POST /api/auth/login)
Step 2 → FE-037 (Findings filters and source/severity tabs) → API-048 (GET /api/findings)
Step 3 → FE-045 (Action detail drawer) → API-006 (GET /api/actions/{action_id})
Step 4 → FE-050 (Create exception modal) → API-040 (POST /api/exceptions)
Final state: User authenticates, reviews findings, and creates an exception when needed.
Failure points: API-012, API-048, API-006, or API-040.

JOURNEY: J3 Inferred — Connect Account and Trigger Ingest
Step 1 → FE-018 (Connect/reconnect AWS account) → API-022 (POST /api/aws/accounts) → AWS-001 (STS:AssumeRole)
Step 2 → FE-023 (Ingest refresh by source) → API-027 (POST /api/aws/accounts/{account_id}/ingest) → JOB-003 (ingest_findings) → AWS-005 (Security Hub:GetFindings)
Step 3 → FE-025 (Ingest progress polling) → API-028 (GET /api/aws/accounts/{account_id}/ingest-progress)
Final state: Account is connected and ingest progress/status is visible to the user.
Failure points: API-022, API-027, JOB-003, AWS-005, or API-028.

JOURNEY: J4 Inferred — Exception Creation Workflow
Step 1 → FE-047 (Remediation strategy selection) → API-007 (GET /api/actions/{action_id}/remediation-options)
Step 2 → FE-050 (Create exception modal) → API-040 (POST /api/exceptions)
Step 3 → FE-055 (Exceptions list and filtering) → API-041 (GET /api/exceptions)
Final state: Exception appears in exceptions list and affects remediation decisions.
Failure points: API-007, API-040, or API-041.

JOURNEY: J5 Inferred — Direct Fix Remediation Run
Step 1 → FE-047 (Remediation strategy selection) → API-007 (GET /api/actions/{action_id}/remediation-options)
Step 2 → FE-049 (Create remediation run) → API-067 (POST /api/remediation-runs) → JOB-011 (remediation_run) → AWS-008 (Security Hub:EnableSecurityHub)
Step 3 → FE-067 (Remediation run live status) → API-071 (GET /api/remediation-runs/{run_id})
Final state: Run reaches terminal success/failure and run detail reflects final outcome.
Failure points: API-067, JOB-011, AWS-008, or API-071.

JOURNEY: J6 Inferred — PR Bundle Plan and Apply
Step 1 → FE-065 (PR bundle summary generation) → API-068 (POST /api/remediation-runs/group-pr-bundle) → JOB-011 (remediation_run)
Step 2 → FE-066 (Online execution controls for generated bundles) → API-074 (POST /api/remediation-runs/{run_id}/execute-pr-bundle) → JOB-012 (execute_pr_bundle_plan) → AWS-001 (STS:AssumeRole)
Step 3 → FE-066 (Online execution controls for generated bundles) → API-075 (POST /api/remediation-runs/{run_id}/approve-apply) → JOB-013 (execute_pr_bundle_apply) → AWS-046 (GuardDuty:ListDetectors)
Step 4 → FE-067 (Remediation run live status) → API-076 (GET /api/remediation-runs/{run_id}/execution)
Final state: Bundle execution state is tracked through plan/apply lifecycle with execution detail.
Failure points: API-068, API-074, API-075, JOB-012, JOB-013, AWS-001, AWS-046, or API-076.

JOURNEY: J7 Inferred — Evidence Export Generation and Download
Step 1 → FE-057 (Evidence/compliance export creation) → API-044 (POST /api/exports) → JOB-014 (generate_export) → AWS-030 (S3:PutObject)
Step 2 → FE-058 (Export history and ad-hoc download) → API-046 (GET /api/exports/{export_id})
Final state: Export is generated and downloadable from export history.
Failure points: API-044, JOB-014, AWS-030, or API-046.

JOURNEY: J8 Inferred — Baseline Report Request and Retrieval
Step 1 → FE-060 (Baseline report viewer page) → API-033 (POST /api/baseline-report) → JOB-015 (generate_baseline_report) → AWS-030 (S3:PutObject)
Step 2 → FE-060 (Baseline report viewer page) → API-035 (GET /api/baseline-report/{report_id})
Final state: Baseline report is available in history and retrievable by report id.
Failure points: API-033, JOB-015, AWS-030, or API-035.

JOURNEY: J9 Additional — SaaS Admin Control-Plane Reconcile
Step 1 → FE-089 (Control-plane reconcile enqueue actions) → API-087 (POST /api/saas/control-plane/reconcile/global) → JOB-009 (reconcile_inventory_shard) → AWS-013 (EC2:DescribeSecurityGroups)
Step 2 → FE-090 (Control-plane reconcile job history) → API-085 (GET /api/saas/control-plane/reconcile-jobs)
Final state: Admin sees reconcile jobs and control-plane status updates for target tenant.
Failure points: API-087, JOB-009, AWS-013, or API-085.

JOURNEY: J10 Additional — Team and Notification Configuration
Step 1 → FE-075 (Team invite) → API-107 (POST /api/users/invite)
Step 2 → FE-077 (Digest notification settings) → API-112 (PATCH /api/users/me/digest-settings)
Step 3 → FE-078 (Slack notification settings) → API-114 (PATCH /api/users/me/slack-settings)
Final state: Team invites and digest/slack notification settings are persisted.
Failure points: API-107, API-112, or API-114.

FEATURE USAGE FREQUENCY

| Feature ID | Feature Name | Used in N journeys | Critical path (yes/no — on the path of every journey) |
|---|---|---|---|
| AWS-001 | STS:AssumeRole | 3 | no |
| API-007 | GET /api/actions/{action_id}/remediation-options | 2 | no |
| API-022 | POST /api/aws/accounts | 2 | no |
| API-027 | POST /api/aws/accounts/{account_id}/ingest | 2 | no |
| API-040 | POST /api/exceptions | 2 | no |
| API-048 | GET /api/findings | 2 | no |
| AWS-005 | Security Hub:GetFindings | 2 | no |
| AWS-030 | S3:PutObject | 2 | no |
| FE-036 | Final checks + queue initial workload | 2 | no |
| FE-037 | Findings filters and source/severity tabs | 2 | no |
| FE-047 | Remediation strategy selection | 2 | no |
| FE-050 | Create exception modal | 2 | no |
| FE-060 | Baseline report viewer page | 2 | no |
| FE-066 | Online execution controls for generated bundles | 2 | no |
| FE-067 | Remediation run live status | 2 | no |
| JOB-003 | ingest_findings | 2 | no |
| JOB-011 | remediation_run | 2 | no |
| API-006 | GET /api/actions/{action_id} | 1 | no |
| API-010 | POST /api/actions/compute | 1 | no |
| API-011 | POST /api/auth/signup | 1 | no |
| API-012 | POST /api/auth/login | 1 | no |
| API-028 | GET /api/aws/accounts/{account_id}/ingest-progress | 1 | no |
| API-033 | POST /api/baseline-report | 1 | no |
| API-035 | GET /api/baseline-report/{report_id} | 1 | no |
| API-041 | GET /api/exceptions | 1 | no |
| API-044 | POST /api/exports | 1 | no |
| API-046 | GET /api/exports/{export_id} | 1 | no |
| API-067 | POST /api/remediation-runs | 1 | no |
| API-068 | POST /api/remediation-runs/group-pr-bundle | 1 | no |
| API-071 | GET /api/remediation-runs/{run_id} | 1 | no |
| API-074 | POST /api/remediation-runs/{run_id}/execute-pr-bundle | 1 | no |
| API-075 | POST /api/remediation-runs/{run_id}/approve-apply | 1 | no |
| API-076 | GET /api/remediation-runs/{run_id}/execution | 1 | no |
| API-085 | GET /api/saas/control-plane/reconcile-jobs | 1 | no |
| API-087 | POST /api/saas/control-plane/reconcile/global | 1 | no |
| API-107 | POST /api/users/invite | 1 | no |
| API-112 | PATCH /api/users/me/digest-settings | 1 | no |
| API-114 | PATCH /api/users/me/slack-settings | 1 | no |
| AWS-008 | Security Hub:EnableSecurityHub | 1 | no |
| AWS-013 | EC2:DescribeSecurityGroups | 1 | no |
| AWS-046 | GuardDuty:ListDetectors | 1 | no |
| FE-006 | Login | 1 | no |
| FE-008 | Signup | 1 | no |
| FE-018 | Connect/reconnect AWS account | 1 | no |
| FE-023 | Ingest refresh by source | 1 | no |
| FE-025 | Ingest progress polling | 1 | no |
| FE-031 | Validate integration role | 1 | no |
| FE-045 | Action detail drawer | 1 | no |
| FE-049 | Create remediation run | 1 | no |
| FE-055 | Exceptions list and filtering | 1 | no |
| FE-057 | Evidence/compliance export creation | 1 | no |
| FE-058 | Export history and ad-hoc download | 1 | no |
| FE-065 | PR bundle summary generation | 1 | no |
| FE-075 | Team invite | 1 | no |
| FE-077 | Digest notification settings | 1 | no |
| FE-078 | Slack notification settings | 1 | no |
| FE-089 | Control-plane reconcile enqueue actions | 1 | no |
| FE-090 | Control-plane reconcile job history | 1 | no |
| JOB-007 | compute_actions | 1 | no |
| JOB-009 | reconcile_inventory_shard | 1 | no |
| JOB-012 | execute_pr_bundle_plan | 1 | no |
| JOB-013 | execute_pr_bundle_apply | 1 | no |
| JOB-014 | generate_export | 1 | no |
| JOB-015 | generate_baseline_report | 1 | no |

ORPHANED FEATURES

| Feature ID | Feature Name | Category | Likely purpose |
|---|---|---|---|
| API-009 | PATCH /api/actions/{action_id} | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-013 | POST /api/auth/logout | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-020 | POST /api/aws/accounts/{account_id}/read-role/update | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-021 | GET /api/aws/accounts/{account_id}/read-role/update-status | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-024 | POST /api/aws/accounts/{account_id}/service-readiness | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-031 | POST /api/aws/accounts/{account_id}/ingest-sync | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-032 | GET /api/aws/accounts/ping | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-037 | GET /api/control-mappings/{mapping_id} | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-042 | GET /api/exceptions/{exception_id} | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-053 | POST /api/internal/reconcile-recently-touched | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-054 | POST /api/internal/group-runs/report | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-055 | POST /api/internal/reconcile-inventory-global | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-056 | POST /api/internal/reconcile-inventory-global-all-tenants | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-057 | POST /api/internal/reconciliation/schedule-tick | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-058 | POST /api/internal/backfill-finding-keys | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-059 | POST /api/internal/backfill-action-groups | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-070 | PATCH /api/remediation-runs/{run_id} | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-078 | GET /api/remediation-runs/{run_id}/pr-bundle.zip | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-084 | GET /api/saas/control-plane/unmatched-report | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-091 | GET /api/saas/tenants/{tenant_id}/users | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-092 | GET /api/saas/tenants/{tenant_id}/aws-accounts | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-093 | GET /api/saas/tenants/{tenant_id}/findings | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-094 | GET /api/saas/tenants/{tenant_id}/actions | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-095 | GET /api/saas/tenants/{tenant_id}/remediation-runs | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-096 | GET /api/saas/tenants/{tenant_id}/exports | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-097 | GET /api/saas/tenants/{tenant_id}/baseline-reports | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-098 | GET /api/saas/tenants/{tenant_id}/notes | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-100 | GET /api/saas/tenants/{tenant_id}/files | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-103 | POST /api/saas/tenants/{tenant_id}/files/upload | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| API-108 | GET /api/users/accept-invite | api | Internal/admin/support endpoint outside mapped user journey coverage. |
| AWS-004 | SQS:GetQueueAttributes | aws-integration | AWS operation used in health/ops paths not traversed by mapped journeys. |
| FE-001 | Root auth router | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-002 | Marketing site nav + hero CTAs | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-003 | FAQ accordion | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-004 | Contact popover panel | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-005 | Locale dropdown | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-011 | Session expiry recovery | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-012 | Global 404 page | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-013 | Global error boundary | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-014 | Sidebar navigation shell | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-015 | Top bar notifications and profile menu | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-016 | Global async banner rail | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-019 | Copy onboarding identifiers in connect modal | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-024 | Ingest refresh all sources | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-028 | Service verification shortcut | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-029 | Onboarding stepper + autosave draft | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-040 | Shared-resource safety confirmation | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-091 | Legacy actions route redirect | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| FE-092 | Legacy action-detail route redirect | frontend | Standalone UI/static or shell flow not traversed by mapped journeys. |
| JOB-001 | worker_queue_poller | job | Maintenance/scheduled/background operation outside mapped journeys. |
| JOB-002 | worker_lambda_handler | job | Maintenance/scheduled/background operation outside mapped journeys. |
| JOB-008 | reconcile_inventory_global_orchestration | job | Maintenance/scheduled/background operation outside mapped journeys. |
| JOB-010 | reconcile_recently_touched_resources | job | Maintenance/scheduled/background operation outside mapped journeys. |
| JOB-017 | backfill_finding_keys | job | Maintenance/scheduled/background operation outside mapped journeys. |
| JOB-018 | backfill_action_groups | job | Maintenance/scheduled/background operation outside mapped journeys. |
