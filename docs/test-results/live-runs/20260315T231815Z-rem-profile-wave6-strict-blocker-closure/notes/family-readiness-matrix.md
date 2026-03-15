# Wave 6 Family Readiness Matrix

- Run ID: `20260315T231815Z-rem-profile-wave6-strict-blocker-closure`
- Date (UTC): `2026-03-15T23:18:15Z`
- Environment used: `local master against a fresh isolated runtime`
- Branch tested: `master`
- Exact HEAD tested: `75fd66b22b003ee58880eaabbfc0626d8a538dd5`
- AWS accounts and regions:
  - SaaS queue/runtime account `029037611564` in `eu-north-1`
  - Isolated AWS test account `696505809372` in `eu-north-1`
- Supported execution model: `customer-run PR bundles only; archived public SaaS-managed plan/apply stayed archived`
- Credential path for customer-run validation:
  - Product/runtime read path: `arn:aws:iam::696505809372:role/CodexP2SecurityHubImportRole`
  - Customer-run apply/rollback path: local AWS CLI profile `test28-root`
  - `role_write_arn` remained `null` and was not used

## Summary

| Family | Executable case ready | Downgrade case ready | Fully ready for full gate | Notes |
| --- | --- | --- | --- | --- |
| `EC2.53` | `Yes` | `Yes` | `Yes` | Unchanged from the March 15 environment-readiness package. |
| `IAM.4` | `Yes` | `Yes` | `Yes` | Unchanged from the March 15 environment-readiness package; `/api/root-key-remediation-runs` remains the only execution authority. |
| `S3.2` | `Yes` | `Yes` | `Yes` | Closed by the March 15 blocker-closure rerun from live `S3.8 -> S3.2` canonical materialization. |
| `S3.5` | `Yes` | `Yes` | `Yes` | Closed by the March 15 blocker-closure rerun after support-tier preservation was fixed. |
| `S3.11` | `Yes` | `Yes` | `Yes` | Closed in this strict package via truthful live `S3.13 -> S3.11` materialization and a real AccessDenied downgrade case. |
| `S3.9` | `Yes` | `Yes` | `Yes` | Unchanged from the March 15 environment-readiness package. |
| `S3.15` | `Yes` | `Yes` | `Yes` | Closed in this strict package via truthful live `S3.17 -> S3.15` materialization and a real customer-managed-KMS downgrade case. |
| `CloudTrail.1` | `Yes` | `Yes` | `Yes` | Unchanged from the March 15 environment-readiness package. |
| `Config.1` | `Yes` | `Yes` | `Yes` | Unchanged from the March 15 environment-readiness package. |

## Families closed in this strict package

### `S3.11`

- Executable case ready: `Yes`
- Downgrade case ready: `Yes`
- Root cause:
  - Current live lifecycle findings now surface on Security Hub control `S3.13`.
  - Current live `S3.11` findings are `event notifications` findings and must be excluded from lifecycle family materialization.
  - The import role has no S3 lifecycle identity-policy reads, so lifecycle evidence depends on bucket resource-policy access.
- Target action IDs / finding IDs / resource IDs:
  - Executable action `a769c380-0bfb-45b7-b358-c41b176521e1`
  - Executable finding `arn:aws:securityhub:eu-north-1:696505809372:security-control/S3.13/finding/186528e9-9ed9-45a6-85b7-df8d21779db0`
  - Executable resource `arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372`
  - Executable run `53eaa411-1407-4966-948a-b8880075ce08`
  - Downgrade action `4f550979-f521-471a-8246-1a24ca7c48d7`
  - Downgrade finding `arn:aws:securityhub:eu-north-1:696505809372:security-control/S3.13/finding/a829dd71-b973-4924-b2e5-2a11d7a31bc1`
  - Downgrade resource `arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372`
  - Downgrade run `7848b5a3-b91a-46b4-b8d7-349dc401c05d`
- Region: `eu-north-1`
- Proof summary:
  - [`../evidence/api/strict-findings-post-fix.txt`](../evidence/api/strict-findings-post-fix.txt) marks `S3.13` lifecycle findings `in_scope = true` with `canonical_control_id = S3.11`.
  - The same evidence file marks current live `S3.11` findings out of scope, preventing event-notification drift from polluting the lifecycle family.
  - [`../evidence/api/strict-action-links-post-fix-current.txt`](../evidence/api/strict-action-links-post-fix-current.txt) shows the lifecycle actions link only to `S3.13` findings after the fix.
  - [`../evidence/api/s311-exec-preview.json`](../evidence/api/s311-exec-preview.json) and [`../evidence/api/s311-exec-run-detail-compact.json`](../evidence/api/s311-exec-run-detail-compact.json) keep the executable case at `deterministic_bundle`.
  - [`../evidence/api/s311-manual-preview.json`](../evidence/api/s311-manual-preview.json) and [`../evidence/api/s311-manual-run-detail-compact.json`](../evidence/api/s311-manual-run-detail-compact.json) truthfully downgrade the manual case to `manual_guidance_only` on `AccessDenied`.
- Truthful conclusion:
  - `S3.11` now has both required proof shapes under current live AWS semantics.
  - The closure comes from truthful live materialization and a truthful runtime downgrade, not from an exception path.

### `S3.15`

- Executable case ready: `Yes`
- Downgrade case ready: `Yes`
- Root cause:
  - Current live SSE-KMS findings now surface on Security Hub control `S3.17`.
  - Current live `S3.15` findings are `Object Lock` findings and must be excluded from the SSE-KMS family.
  - The import role identity policy has no KMS reads, and the seeded customer-managed key path does not provide policy/grant evidence, so the customer-managed branch must downgrade.
- Target action IDs / finding IDs / resource IDs:
  - Executable action `a6585d13-e010-415e-823c-334a4c40bdf8`
  - Executable finding `arn:aws:securityhub:eu-north-1:696505809372:security-control/S3.17/finding/3e164775-f8b9-498f-9e33-9d3e3b29c0fd`
  - Executable resource `arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372`
  - Executable run `38ed8b33-1737-4601-a491-e9d428eafc5e`
  - Downgrade action `9405f465-5b90-4fee-b4f7-030660683e52`
  - Downgrade finding `arn:aws:securityhub:eu-north-1:696505809372:security-control/S3.17/finding/ce87ea38-d12a-4c80-9e33-afb7a361c4b7`
  - Downgrade resource `arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372`
  - Downgrade run `8f441c77-9eca-49a1-af8f-853b17f429c6`
- Region: `eu-north-1`
- Proof summary:
  - [`../evidence/api/strict-findings-post-fix.txt`](../evidence/api/strict-findings-post-fix.txt) marks `S3.17` SSE-KMS findings `in_scope = true` with `canonical_control_id = S3.15`.
  - The same evidence file marks current live `S3.15` findings out of scope, preventing Object Lock drift from materializing as SSE-KMS actions.
  - [`../evidence/api/strict-action-links-post-fix-current.txt`](../evidence/api/strict-action-links-post-fix-current.txt) shows the SSE-KMS actions link only to `S3.17` findings after the fix.
  - [`../evidence/api/s315-exec-preview.json`](../evidence/api/s315-exec-preview.json) and [`../evidence/api/s315-exec-run-detail-compact.json`](../evidence/api/s315-exec-run-detail-compact.json) keep the AWS-managed executable case at `deterministic_bundle`.
  - [`../evidence/api/s315-manual-preview.json`](../evidence/api/s315-manual-preview.json) and [`../evidence/api/s315-manual-run-detail-compact.json`](../evidence/api/s315-manual-run-detail-compact.json) truthfully downgrade the customer-managed branch to `review_required_bundle` on `AccessDeniedException`.
- Truthful conclusion:
  - `S3.15` now has both required proof shapes under current live AWS semantics.
  - The customer-managed-KMS safety boundary remains fail-closed and was not relaxed to force readiness.

## Carry-over families from the March 15 evidence packages

- `EC2.53`, `IAM.4`, `S3.9`, `CloudTrail.1`, and `Config.1` keep the ready status and exact proof references already recorded in:
  - [`../20260315T201821Z-rem-profile-wave6-environment-readiness/notes/family-readiness-matrix.md`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T201821Z-rem-profile-wave6-environment-readiness/notes/family-readiness-matrix.md)
- `S3.2` and `S3.5` keep the ready status and exact proof references already recorded in:
  - [`../20260315T213821Z-rem-profile-wave6-readiness-rerun/notes/family-readiness-matrix.md`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T213821Z-rem-profile-wave6-readiness-rerun/notes/family-readiness-matrix.md)
- This strict closure package does not invalidate any of those earlier ready cases.
- Net full-gate status after combining the March 15 baseline, rerun, and strict closure package:
  - `9` families fully ready
  - `0` executable-only families
  - `0` blocked families
