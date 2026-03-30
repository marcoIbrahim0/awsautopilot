# Live E2E Run Metadata

- Run ID: `20260326T132117Z-phase5-pending-confirmation-repair`
- Created at (UTC): `2026-03-26T13:21:17Z`
- Frontend URL: `https://ocypheris.com`
- Backend URL: `https://api.ocypheris.com`
- Live tenant: `Valens Local Backup`
- Live account: `696505809372`
- Live region: `eu-north-1`
- Active runtime deploy tag: `20260326T125504Z`
- API Lambda image after deploy: `029037611564.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-dev-saas-api:20260326T125504Z`
- Worker Lambda image after deploy: `029037611564.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-dev-saas-worker:20260326T125504Z`
- Repaired control family: `Config.1`
- Live repair result: `PASS`

## Repair Sequence

1. `POST /api/internal/pending-confirmation/sweep`
   - `200`
   - returned `evaluated_states=0`, `due_states=0`, `enqueued_scopes=0`
2. `POST /api/aws/accounts/696505809372/ingest`
   - `202`
   - queued Security Hub refresh message `f6e3a9f1-8536-4125-b6b0-24fe8be5d35d`
3. `POST /api/internal/reconcile-inventory-global`
   - `200`
   - skipped by prereqs with `control_plane_stale` and `prerequisite_check_error`
4. `POST /api/internal/reconcile-inventory-shard`
   - `200`
   - queued one targeted `config` shard
5. `GET /api/findings/dd46ab79-1ea5-4ea7-a754-0d5e7335cbc1`
   - returned `RESOLVED` with `pending_confirmation=false`

## Before / After

- Before repair:
  - `status=NEW`
  - `shadow.status_normalized=OPEN`
  - `shadow.status_reason=inventory_confirmed_non_compliant`
  - `pending_confirmation=true`
  - `followup_kind=awaiting_aws_confirmation`
- After repair:
  - `status=RESOLVED`
  - `effective_status=RESOLVED`
  - `shadow.status_normalized=RESOLVED`
  - `shadow.status_reason=inventory_confirmed_compliant`
  - `pending_confirmation=false`
  - `followup_kind=null`

## Related Phase 5 Evidence

- Full backup-tenant rerun:
  - [20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun/README.md)
- Focused CloudTrail postdeploy recheck:
  - [20260326T052354Z-phase5-cloudtrail-postdeploy-recheck](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T052354Z-phase5-cloudtrail-postdeploy-recheck/README.md)
