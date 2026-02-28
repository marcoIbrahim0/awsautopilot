---
Test 07 — AWS Account Connection Validation
Run date: 2026-02-28
Status: FAIL

ENVIRONMENT VALUES
BACKEND_API_URL=https://api.valensjewelry.com
ADMIN_TOKEN_SOURCE=docs/test-results/test-01-api-health.md
TEST_ACCOUNT_ID=029037611564
READ_ROLE_ARN=arn:aws:iam::029037611564:role/SecurityAutopilotReadRole
WRITE_ROLE_ARN=arn:aws:iam::029037611564:role/SecurityAutopilotWriteRole
CONNECTED_ACCOUNT_ID=cdc6355d-2f56-4f19-b8de-a200ed521c07

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 7.1 List existing accounts | HTTP `200`, array returned | HTTP `200`; returned array with existing account (`account_id=029037611564`) | PASS |
| 7.2 Empty body rejected | HTTP `400` or `422` | HTTP `422` | PASS |
| 7.3 Invalid account ID format rejected | HTTP `400` or `422` | HTTP `422` | PASS |
| 7.4 Malformed ARN rejected | HTTP `400` or `422` | HTTP `422` | PASS |
| 7.5 Check if test account already connected | Existing account id found if already connected | Found existing account id `cdc6355d-2f56-4f19-b8de-a200ed521c07` | PASS |
| 7.6 Connect test AWS account (if not connected) | HTTP `200` or `201` with account object | Skipped, because account was already connected in 7.5 | PASS (SKIPPED AS DESIGNED) |
| 7.7 Duplicate account connection rejected | HTTP `400` or `409` | HTTP `422` | FAIL |

Failed tests:
* 7.7 Duplicate account connection rejected (expected `400/409`, got `422`)

Blocking for go-live: yes
Notes:
* Requested source file `docs/test-results/test-01-environment.md` was not present; environment values were loaded from `docs/test-results/test-01-api-health.md`.
* `docs/prod-readiness/08-deployment-report.md` contained `TEST_ACCOUNT_ID` but did not explicitly include `READ_ROLE_ARN`/`WRITE_ROLE_ARN`; those were resolved using standard role naming for the same account.
---
