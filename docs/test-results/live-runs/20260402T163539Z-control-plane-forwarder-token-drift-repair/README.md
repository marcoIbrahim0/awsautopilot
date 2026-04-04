# Control-plane forwarder token-drift repair on April 2, 2026 UTC

Status: `PASS`. The remaining stale-readiness issue for account `696505809372` was a customer forwarder delivery/auth drift problem, not a reopened `S3.5` remediation bug and not a broken SaaS readiness path.

## Scope

- Account: `696505809372`
- Tenant: `9f7616d8-af04-43ca-99cd-713625357b70`
- User: `7c43e0b3-6e98-43af-826f-f4eeaa5af674`
- Regions: `eu-north-1`, `us-east-1`
- SaaS API: `https://api.ocypheris.com`
- Forwarder stack: `SecurityAutopilotControlPlaneForwarder`
- Protected already-closed action: `3970aa2f-edc5-4870-87bd-fa986dad3d98`
- Protected already-closed finding: `69507c08-bbb8-491d-9ec0-543278d96a2b`

## Key Outcomes

- The real fault domain was reduced to the customer EventBridge forwarder path:
  - historical EventBridge metrics show real allowlisted events were matching and invoking before repair while `FailedInvocations` was non-zero
  - synthetic SaaS-side intake had already proven the readiness path itself still worked
- Customer forwarder stacks were refreshed in both regions with the current tenant control-plane token and current repo template.
- Fresh retained post-repair evidence shows both customer connection secrets now match the tenant's current `control_plane_token_fingerprint`.
- Fresh retained real-event proof shows account-level `PutAccountPublicAccessBlock` events advanced readiness truthfully in both regions without relying on synthetic-only success.
- Fresh retained current-state proof shows the earlier `S3.5` action/finding remain resolved, so this task did not reopen the closed remediation bundle bug.
- The repo now includes a narrow production guardrail in `scripts/verify_control_plane_forwarder.sh` plus focused tests so future operator verification fails fast on forwarder token drift before customers see stale readiness again.

## Important Evidence

- Final summary: `notes/final-summary.md`
- Request inputs: `notes/request-inputs.json`
- Run window: `notes/run-window.json`
- Tenant/API state:
  - `evidence/api/auth-me-postrepair.json`
  - `evidence/api/readiness-postrepair.json`
  - `evidence/api/actions-list-s35-current.json`
  - `evidence/api/findings-list-s35-current.json`
- DB freshness and protected-state proof:
  - `evidence/db/control-plane-ingest-status-postrepair.tsv`
  - `evidence/db/control-plane-events-postrepair.json`
  - `evidence/db/s35-state-postrepair.json`
- Real AWS event proof:
  - `evidence/aws/cloudtrail-put-account-public-access-block-eu-north-1.json`
  - `evidence/aws/cloudtrail-put-account-public-access-block-us-east-1.json`
- Forwarder shape and token audit:
  - `evidence/aws/forwarder-stack-eu-north-1.json`
  - `evidence/aws/forwarder-stack-us-east-1.json`
  - `evidence/aws/forwarder-stack-resources-eu-north-1.json`
  - `evidence/aws/forwarder-stack-resources-us-east-1.json`
  - `evidence/aws/connection-token-match-eu-north-1.json`
  - `evidence/aws/connection-token-match-us-east-1.json`
  - `evidence/aws/verify-forwarder-eu-north-1.txt`
  - `evidence/aws/verify-forwarder-us-east-1.txt`
- EventBridge metrics:
  - `evidence/metrics/pre-repair-eu-north-1.json`
  - `evidence/metrics/pre-repair-us-east-1.json`
  - `evidence/metrics/post-repair-eu-north-1.json`
  - `evidence/metrics/post-repair-us-east-1.json`
- SaaS logs:
  - `evidence/logs/api-window.json`
  - `evidence/logs/worker-window.json`

## Conclusion

The stale control-plane freshness issue is now closed for the real live path. Real allowlisted upstream events again refresh `control_plane_event_ingest_status` truthfully in both configured regions, both customer forwarder connections match the current tenant token, and the already-resolved `S3.5` action/finding remain resolved.
