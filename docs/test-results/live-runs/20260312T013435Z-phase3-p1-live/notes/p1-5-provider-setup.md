# P1.5 Provider Setup

- `GET /api/integrations/settings` returned `404 {"detail":"Not Found"}` on live.
- Production database inspection shows these tables are missing:
  - `tenant_integration_settings`
  - `action_external_links`
  - `integration_sync_tasks`
  - `integration_event_receipts`
- Result:
  - No live provider configuration can be discovered for `jira`, `servicenow`, or `slack`.
  - No provider sandbox/test setup is reachable because the Phase 3 P1.5 route and persistence layer are not present on the deployed runtime.

Supporting evidence:
- `../evidence/api/p1-5-settings-list.headers.txt`
- `../evidence/api/p1-5-settings-list.body.json`
- `../evidence/db/table-existence.txt`
- `../evidence/api/runtime-api-function.json`
