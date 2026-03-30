# Run Metadata

- Run ID: `20260328T163848Z-remediation-determinism-phase1-production-live`
- Started from workspace: `/Users/marcomaher/AWS Security Autopilot`
- API base: `https://api.ocypheris.com`
- Tenant name: `Marco`
- Tenant ID: `e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`
- Authenticated user: `marco.ibrahim@ocypheris.com`
- Canary account: `696505809372`
- Region: `eu-north-1`
- AWS profile used for local Terraform validation: `test28-root`
- Prior local Phase 1 gate package:
  - [20260328T162829Z-remediation-determinism-phase1-production](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T162829Z-remediation-determinism-phase1-production/README.md)

## Production Actions Exercised

- `WI-3`
  - action `456f845e-da64-43cf-8dc2-d738c3a770df`
  - remediation run `d16be6ee-2297-41c2-88b4-5dbac9ade2b6`
- `WI-6`
  - action `19a9b0f0-de47-4a5b-982f-8d3c876c2064`
  - remediation run `83461a94-e216-48bf-8a38-d4900fe657a5`

## Required Phase 1 Coverage Still Missing

- `WI-7`
- `WI-12`
- `WI-13`
- `WI-14`

## Evidence Notes

- Production auth succeeded only when the login request used a browser-like user agent through `curl`; the Python no-UI client path still hit Cloudflare `1010 browser_signature_banned`
- No AWS apply was executed because both generated Terraform bundles failed `terraform validate`
