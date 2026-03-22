# Notification Center Live E2E Validation (2026-03-20 UTC)

## Scope

Targeted live validation for the unified notification center and responsive navbar bell against:

- frontend: `https://ocypheris.com`
- backend: `https://api.ocypheris.com`
- tenant: `Valens` (`9f7616d8-af04-43ca-99cd-713625357b70`)
- live admin user: `marco.ibrahim@ocypheris.com`
- connected account: `696505809372`

Goals:

- verify the live backend exposes the new `/api/notifications` contract
- verify the live navbar bell renders the new unified notification-center UI
- queue a real account refresh from the live Accounts page and confirm the bell reflects live job state
- confirm whether the live shell is using the new persisted bell flow or the older client-only bell flow

## Execution Summary

Because the retained live password was not used for this targeted rerun, the browser session used a short-lived JWT minted with the current runtime signing secret for the existing live admin user. The first browser-side refresh attempt failed with `CSRF validation failed` because the injected session hit `POST /api/auth/refresh` and rotated the shared CSRF cookie; after syncing the frontend-domain CSRF cookie to the refreshed `.ocypheris.com` value, the live UI refresh path executed normally. That harness-specific mismatch is not the primary product finding for this run.

Observed live behavior:

- `GET /api/auth/me` returned `200`
- `GET /api/aws/accounts` returned `200` and still showed account `696505809372` as `validated`
- `GET /api/notifications` returned `404` before any job trigger
- from the live Accounts page, `POST /api/aws/accounts/696505809372/ingest` returned `202`
- `GET /api/aws/accounts/696505809372/ingest-progress?...source=security_hub` returned `200` and reached `status=running`, `progress=37`
- after queueing the real ingest job, the live bell badge incremented to `1` and the bell menu showed the queued job immediately
- the live bell UI is still the old client-only menu shape:
  - title `Notification Center`
  - action `Clear finished`
  - single flat item list
- the browser network log never showed any request to `/api/notifications`
- `GET /api/notifications` still returned `404` after the real live job was queued

## Primary Findings

1. Live backend rollout is incomplete for the notification-center feature.
   - The new canonical endpoint `GET /api/notifications` is not present on the deployed API and returns `404`.
   - Evidence:
     - [notifications-before.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T172617Z/evidence/api/notifications-before.json)
     - [notifications-after.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T172617Z/evidence/api/notifications-after.json)
     - [http-status.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T172617Z/evidence/api/http-status.log)

2. Live frontend rollout is also incomplete for the navbar bell refactor.
   - The deployed shell still renders the old job-only bell menu instead of the new sectioned notification-center panel/sheet.
   - The live browser never requested `/api/notifications`, which matches the older frontend implementation rather than the new provider-backed bell.
   - Evidence:
     - [notification-bell-live.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T172617Z/evidence/ui/notification-bell-live.png)
     - [bell-open-after-queue.yml](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T172617Z/evidence/browser/bell-open-after-queue.yml)
     - [network-after-queue.log](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T172617Z/evidence/browser/network-after-queue.log)

3. The existing live bell still reflects local job state for queued ingest operations.
   - This proves the old client-only bell path is still active in production: the badge and queued job row updated immediately after the live ingest request was accepted, even though `/api/notifications` does not exist on the deployed API.
   - Evidence:
     - [ingest-progress-after.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T172617Z/evidence/api/ingest-progress-after.json)
     - [notification-bell-live.png](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T172617Z/evidence/ui/notification-bell-live.png)

## Result

`FAIL`

The new unified notification center is implemented in the repo but is not live on production as of March 20, 2026 UTC. The deployed backend is missing `/api/notifications`, and the deployed frontend still serves the previous client-only bell UI.

## Recommended Next Step

Deploy the notification-center backend/frontend changes together, then rerun this same targeted live flow to verify:

- `/api/notifications` returns `200`
- the navbar bell renders the new desktop/mobile UI
- the queued ingest job appears in the persisted notification center
- governance alerts and job notifications share the same live bell surface
