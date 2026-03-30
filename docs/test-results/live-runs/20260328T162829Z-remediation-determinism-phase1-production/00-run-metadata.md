# Run Metadata

- Run ID: `20260328T162829Z-remediation-determinism-phase1-production`
- Executed on: `2026-03-28`
- API base: `https://api.ocypheris.com`
- Production runtime only: `yes`
- Isolated current-head fallback allowed: `no`
- Scope: Phase 1 only
- Phase 1 WIs:
  - `WI-3`
  - `WI-6`
  - `WI-7`
  - `WI-12`
  - `WI-13`
  - `WI-14`
- Target AWS account: `696505809372`
- Target region: `eu-north-1`
- Required grouped proof: `yes`
- Final outcome: `BLOCKED`

## Gate 0 Checks

- `GET /health` on `https://api.ocypheris.com`: `200`
- `GET /ready` on `https://api.ocypheris.com`: `200`
- default local AWS identity: account `029037611564`, user `AutoPilotAdmin`
- canary AWS identity via `AWS_PROFILE=test28-root`: account `696505809372`, principal `arn:aws:iam::696505809372:root`
- direct assume-role from `AutoPilotAdmin` to `arn:aws:iam::696505809372:role/OrganizationAccountAccessRole`: `AccessDenied`

## Operator Auth Attempts

1. `POST /api/auth/login` for `marco.ibrahim@ocypheris.com`
   - result: `{"detail":"Invalid email or password"}`
2. `POST /api/auth/login` for `maromaher54@gmail.com`
   - result: `{"detail":"email_verification_required", ...}`
3. `GET /api/auth/me` using the retained March 23, 2026 `Valens` bearer
   - result: `{"detail":"User not found"}`
4. Fallback DB connectivity check through `config/.env.ops`
   - result: Neon quota error: `Your project has exceeded the data transfer quota`

## Local Gate Coverage

The full documented Phase 1 local gate was executed and retained under `local-gate/`.

- total commands: `11`
- passed: `11`
- failed: `0`

## Blocking Condition

The run stopped before any authenticated production action selection, preview, create, bundle generation, grouped execution, recompute, or rollback steps because the workspace had no valid current production operator auth path.
