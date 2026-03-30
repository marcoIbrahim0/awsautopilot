# Phase 5 Pending-Confirmation Repair

- Run ID: `20260326T132117Z-phase5-pending-confirmation-repair`
- Date (UTC): `2026-03-26`
- Frontend: `https://ocypheris.com`
- API: `https://api.ocypheris.com`
- Live tenant/account used: tenant `Valens Local Backup`, account `696505809372`, region `eu-north-1`
- Runtime deploy tags already active: `20260326T125504Z` for API and worker
- Outcome: `PASS`
- Verification focus: `Config.1` stale pending-confirmation repair

## Summary

This retained repair run closed the last remaining March 26 Phase 5 blocker after AWS had already reevaluated the backup-tenant `Config.1` finding but the production app still showed `status=NEW` and `pending_confirmation=true`.

The deployed pending-confirmation sweep was healthy, but it returned zero due states for this legacy action because the stale row predated the new scheduling fields and its 12-hour confirmation window had already expired. A one-time account-scoped `ingest` refresh also produced no Security Hub row updates. The stale state finally cleared after a targeted `config` inventory-reconcile shard refreshed the shadow evidence for account `696505809372` in `eu-north-1`.

## Live Outcome

- finding: `dd46ab79-1ea5-4ea7-a754-0d5e7335cbc1`
- remediation action: `84f874b0-d2fd-405f-87fb-edc3264601a2`
- action group: `03352204-291a-4b40-bfc6-9913c42148ac`
- post-repair finding state:
  - `status=RESOLVED`
  - `effective_status=RESOLVED`
  - `last_observed_at=2026-03-26T12:25:03.778000+00:00`
  - `resolved_at=2026-03-26T12:25:03.778000+00:00`
  - `pending_confirmation=false`
  - `followup_kind=null`
- post-repair shadow state:
  - `status_normalized=RESOLVED`
  - `status_reason=inventory_confirmed_compliant`
- post-repair action group bucket:
  - `run_successful_confirmed`

## Key Artifacts

- [Run metadata](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T132117Z-phase5-pending-confirmation-repair/00-run-metadata.md)
- [Final summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T132117Z-phase5-pending-confirmation-repair/notes/final-summary.md)
- [Structured summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T132117Z-phase5-pending-confirmation-repair/summary.json)
- [Post-repair finding payload](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T132117Z-phase5-pending-confirmation-repair/api/config_finding_post_repair.json)
- [Repair call responses](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T132117Z-phase5-pending-confirmation-repair/internal/repair_responses.json)
- [Superseded partial Phase 5 rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun/README.md)
