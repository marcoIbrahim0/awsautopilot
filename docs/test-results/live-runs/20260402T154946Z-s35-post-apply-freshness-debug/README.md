# S3.5 post-apply freshness debug on April 2, 2026 UTC

Status: `PASS` for bounded issue reduction. No new `S3.5` product regression was reproduced, and the remaining stale-readiness issue reduced to missing fresh upstream control-plane events rather than a current compute/reconcile/materialization bug.

## Scope

- Account: `696505809372`
- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- User: `7c43e0b3-6e98-43af-826f-f4eeaa5af674`
- Region focus: `eu-north-1`
- Action: `3970aa2f-edc5-4870-87bd-fa986dad3d98`
- Bucket: `arch1-bucket-evidence-b1-696505809372-eu-north-1`

## Key Outcomes

- Raw AWS still shows the safe applied policy state for the bucket:
  - preserved CloudFront `AllowCloudFrontReadOnly`
  - added `DenyInsecureTransport`
  - bucket Public Access Block still enabled
- Fresh live API checks show the action and finding remain truthfully resolved before and after:
  - `POST /api/aws/accounts/696505809372/ingest`
  - `POST /api/actions/compute`
  - `POST /api/actions/reconcile`
- The earlier retained generic/global reconcile `IntegrityError` did not reproduce in this run window.
- Control-plane readiness still started stale in both configured regions because `control_plane_event_ingest_status` had not advanced since March 24, 2026 UTC.
- Supported synthetic control-plane events for `eu-north-1` and `us-east-1` immediately flipped readiness to green, proving the current product pipeline can update readiness when fresh control-plane input arrives.

## Important Evidence

- Final summary: `notes/final-summary.md`
- Request inputs: `notes/request-inputs.json`
- Run window: `notes/run-window.json`
- Raw AWS reconfirmation:
  - `evidence/aws/pre-verify-bucket-policy.json`
  - `evidence/aws/pre-verify-public-access-block.json`
- Required live API flow:
  - `evidence/api/account-ingest.json`
  - `evidence/api/actions-compute.json`
  - `evidence/api/readiness-pre.json`
  - `evidence/api/actions-list-pre.json`
  - `evidence/api/findings-list-pre.json`
  - `evidence/api/readiness-reconcile-post-60s.json`
  - `evidence/api/actions-list-reconcile-post-60s.json`
  - `evidence/api/findings-list-reconcile-post-60s.json`
- Control-plane freshness evidence:
  - `evidence/api/control-plane-ingest-status.tsv`
  - `evidence/api/control-plane-synthetic-event-eu-north-1.json`
  - `evidence/api/control-plane-synthetic-event-us-east-1.json`
  - `evidence/api/readiness-post-synthetic.json`
  - `evidence/api/control-plane-ingest-status-post-synthetic.tsv`
- Log windows:
  - `evidence/logs/api-window.json`
  - `evidence/logs/worker-window.json`
  - `evidence/logs/api-synthetic-window.json`

## Conclusion

The bounded remaining issue is now explicit: account `696505809372` is not producing fresh live control-plane readiness signal on its own. The `S3.5` bundle path remains closed correctly, the product-facing action/finding state remains truthful, and the current runtime updates readiness immediately when fed fresh control-plane input through the supported synthetic route.
