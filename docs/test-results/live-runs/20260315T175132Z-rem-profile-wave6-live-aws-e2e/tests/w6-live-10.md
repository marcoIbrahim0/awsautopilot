# Test 10 - Config.1 migration boundaries

- Wave: `Wave 6`
- Date (UTC): `2026-03-15T18:06:54Z`
- Tester: `Codex`
- Frontend URL: `N/A (API-only isolated local runtime)`
- Backend URL: `http://127.0.0.1:18012`

## Preconditions

- Identity: `isolated local admin user`
- Tenant: `a2805c66-3117-430d-9ab5-699835441dda`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`
- Required prior artifacts: `action_id=d0daa0c3-4a22-4dfc-9db2-aef91ab9c27c`

## Steps Executed

1. Reviewed Config options before and after tenant default injection.
2. Confirmed `config_enable_account_local_delivery` resolved to `deterministic_bundle`.
3. Confirmed `config_enable_centralized_delivery` consumed the tenant default bucket but downgraded to `review_required_bundle` on bucket-policy proof failure.
4. Attempted create without `risk_acknowledged` for both branches and observed the explicit acknowledgment gate.
5. Re-ran both creates with `risk_acknowledged=true`, fetched run details, and inspected the generated bundles.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | `GET` | `/api/actions/d0daa0c3-4a22-4dfc-9db2-aef91ab9c27c/remediation-options` | none | `200` | Compatibility strategies remained `config_enable_account_local_delivery`, `config_enable_centralized_delivery`, and `config_keep_exception` | `2026-03-15T18:04:50Z` | `../evidence/api/d0daa0c3-4a22-4dfc-9db2-aef91ab9c27c-options.json` |
| 2 | `GET` | `/api/actions/d0daa0c3-4a22-4dfc-9db2-aef91ab9c27c/remediation-options` | none after settings update | `200` | Tenant default bucket was consumed; centralized delivery downgraded on `403` while local delivery stayed deterministic | `2026-03-15T18:05:02Z` | `../evidence/api/d0daa0c3-4a22-4dfc-9db2-aef91ab9c27c-options-after-settings.json` |
| 3 | `GET` | `/api/actions/d0daa0c3-4a22-4dfc-9db2-aef91ab9c27c/remediation-preview` | local-delivery preview | `200` | Preview resolution was `deterministic_bundle` | `2026-03-15T18:05:08Z` | `../evidence/api/w6-live-10-config-local-preview.json` |
| 4 | `GET` | `/api/actions/d0daa0c3-4a22-4dfc-9db2-aef91ab9c27c/remediation-preview` | centralized-delivery preview | `200` | Preview resolution was `review_required_bundle` with bucket-policy proof blockers | `2026-03-15T18:05:08Z` | `../evidence/api/w6-live-10-config-central-preview.json` |
| 5 | `POST` | `/api/remediation-runs` | local-delivery create without risk acknowledgement | `400` | Explicit `Risk acknowledgement required` gate fired for the deterministic branch | `2026-03-15T18:05:13Z` | `../evidence/api/w6-live-10-config-local-create-request.json`, `../evidence/api/w6-live-10-config-local-create-response.json` |
| 6 | `POST` | `/api/remediation-runs` | local-delivery create with `risk_acknowledged=true` | `201` | Deterministic Config bundle was accepted | `2026-03-15T18:06:06Z` | `../evidence/api/w6-live-10-config-local-create-ack-request.json`, `../evidence/api/w6-live-10-config-local-create-ack-response.json` |
| 7 | `GET` | `/api/remediation-runs/49103000-1104-4a36-8757-8e243e883dc5` | none | `200` | Run detail persisted `support_tier=deterministic_bundle` | `2026-03-15T18:06:06Z` | `../evidence/api/w6-live-10-config-local-run-detail.json` |
| 8 | `POST` | `/api/remediation-runs` | centralized-delivery create with `risk_acknowledged=true` | `201` | Review-tier centralized Config bundle was accepted | `2026-03-15T18:06:54Z` | `../evidence/api/w6-live-10-config-central-create-ack-request.json`, `../evidence/api/w6-live-10-config-central-create-ack-response.json` |
| 9 | `GET` | `/api/remediation-runs/e1a04e3f-d39e-47d5-b6ab-1539af58a2f5` | none | `200` | Run detail persisted `support_tier=review_required_bundle` for centralized delivery | `2026-03-15T18:06:54Z` | `../evidence/api/w6-live-10-config-central-run-detail.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `Not exercised` | `N/A` | `API-only validation` | `N/A` |

## Assertions

- Positive path: `pass` — the resolver, preview, create, and run-detail surfaces consistently kept `config_enable_account_local_delivery` deterministic.
- Negative path: `pass` — centralized delivery downgraded explicitly after tenant defaults were consumed, and `config_keep_exception` remained compatible in options metadata.
- Auth boundary: `not exercised in this test`
- Contract shape: `pass` — public strategy compatibility was preserved, canonical `artifacts.resolution` persisted, and both branches required explicit risk acknowledgement where appropriate.
- Idempotency/retry: `not exercised`
- Auditability: `pass` — before/after options, previews, create responses, run details, and both extracted bundles were saved.

## Result

- Status: `PARTIAL`
- Severity (if issue found): `🔴 BLOCKING`
- Primary tracker mapping: `Wave 6 / W6-LIVE-10`

## Tracker Updates Applied

- Quick Status Board updated: `no`
- Section 8 go-live checkbox updated: `no`
- Section 9 changelog update required: `no`

## Notes

- This run proved the product-side deterministic and review branches for `Config.1` on current `master`.
- The family still cannot be marked fully validated because no operator-owned/test-account write credentials were available to manually apply the deterministic bundle and verify AWS-side rollback in the isolated account.

