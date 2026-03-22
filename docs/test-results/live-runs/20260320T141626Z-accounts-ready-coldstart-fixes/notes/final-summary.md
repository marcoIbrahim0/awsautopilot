# Accounts React / Ready / Cold-Start Cleanup Summary

## Scope

This retained run closes the March 20, 2026 residual live issues called out after the template rollout recovery:

1. Accounts page React production error `#418`
2. `/ready` queue-lag `cloudwatch:GetMetricStatistics` access-denied noise
3. Post-deploy API Lambda init-time timeout bursts

Frontend target: `https://ocypheris.com`  
Backend target: `https://api.ocypheris.com`

## Result

Status: `PASS`

- Accounts page renders cleanly with no browser console errors or warnings after the shared link-style CTA refactor plus tenant-ID hydration fix.
- `/ready` stays `200` / `ready=true` and now returns queue-lag metrics without raw AWS authorization errors.
- The post-deploy API Lambda log window shows `0` fresh timeout/import errors after the lazy first-invoke runtime bootstrap change.

## Key Evidence

### Accounts UI

- Clean overview screenshot: `evidence/screenshots/accounts-postfix-clean.png`
- Clean detail modal screenshot: `evidence/screenshots/accounts-postfix-detail-modal.png`
- Browser console before/after modal:  
  - `evidence/ui/accounts-console-postfix.json`  
  - `evidence/ui/accounts-console-postfix-after-modal.json`
- Browser network capture proving authenticated API traffic during the Accounts pass: `evidence/ui/accounts-network-postfix.json`
  - `GET https://api.ocypheris.com/api/auth/me => 200`
  - `GET https://api.ocypheris.com/api/aws/accounts => 200`

### API Health / Readiness

- `evidence/api/health-postfix-20260320T144924Z.json`
- `evidence/api/ready-postfix-20260320T144924Z.json`

Observed `/ready` result:

- `ready=true`
- all required queues `ready=true`
- all queue `oldest_message_age_seconds=0.0`
- no raw `AccessDenied` / `cloudwatch:GetMetricStatistics` text in the response body

### Lambda Post-Deploy Log Window

- Detailed post-deploy window: `evidence/runtime/api-postfix-log-window-detailed.txt`
- Summary extraction: `evidence/runtime/api-postfix-summary.json`

Observed post-deploy behavior after the lazy-bootstrap deploy at `2026-03-20T14:47:46Z`:

- `postfix_timeout_events = 0`
- no `Runtime.ImportModuleError`
- no `Task timed out`
- cold environments still emitted normal `Init Duration` lines, but they were small and successful:
  - `595.09 ms`
  - `207.37 ms`
  - `216.44 ms`

## Notes

- The specific failure mode we were closing was the Lambda init-phase timeout burst. That issue is no longer present in this retained window.
- First cold requests still pay real bootstrap cost on invoke. The slowest retained request in this run was `12.26s` with `Init Duration: 595.09 ms`, which means the bootstrap cost has been shifted out of init and into the first invoke path as intended. That is acceptable for this closure, but it remains a future latency optimization target.
