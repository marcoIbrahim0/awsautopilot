# Test 19

- Wave: 06
- Focus: Slack/digest settings and webhook security validation
- Status: PASS
- Severity (if issue): N/A

## Preconditions

- Identity: Tenant A admin/member tokens reused from prior live evidence and revalidated via `GET /api/auth/me`; fresh Tenant B admin created for isolated mutable-settings probes in each run.
- Tenant: Tenant A `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`) for auth-boundary probes; Tenant B from initial run (`Wave6 Test19 TenantB 20260301T011253Z`, `tenant_id=23e5f0c8-0098-45d0-99a2-269b39394319`) and fresh rerun Tenant B (`Wave6 Test19 Rerun 20260301T015756Z`) for digest/Slack mutation and webhook security probes.
- AWS account: `029037611564`.
- Region(s): `eu-north-1`.
- Prerequisite IDs/tokens: `test-14-00-login-admin.json` (admin token), `20260228T182055Z/evidence/api/test-08-rerun-postdeploy-accept-invite-valid-token.json` (member token), Tenant B tokens from `test-19-live-20260301T011252Z-03-signup-tenantb.json` and `test-19-rerun-20260301T015756Z-03-signup-tenantb.json`.
- Deployment precondition: runtime redeployed with profile `AWS_PROFILE=default TENANT_RECONCILIATION_ENABLED=false CONTROL_PLANE_SHADOW_MODE=true ./scripts/deploy_saas_serverless.sh --enable-worker true --worker-reserved-concurrency 1` (image tag `20260301T014806Z`) before rerun probes.

## Steps Executed

1. Revalidated admin/member auth context, then created fresh Tenant B to avoid mutating unknown existing Slack webhook secrets in Tenant A.
2. Executed `GET/PATCH` digest-settings flow (toggle, recipient set/clear, repeat patch) and validated persistence by immediate reload.
3. Executed `GET/PATCH` Slack-settings flow (toggle, valid hooks URL, clear) and validated persistence by immediate reload.
4. Executed auth-boundary probes for both settings endpoints (`member` and `no-auth`).
5. Executed webhook security probes for non-Slack and SSRF-style URLs (`example.com`, metadata IP, hooks lookalike domain) and recorded accept/reject behavior.
6. Re-ran the full matrix post-deploy and generated fresh contract/persistence/security summaries (`test-19-rerun-20260301T015756Z-*`) for closure verification.

## API Evidence

| # | Method | Endpoint | Request Payload | HTTP | Response Summary | Timestamp (UTC) | Artifact Path |
|---|---|---|---|---|---|---|---|
| 1 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <admin_token>` | `200` | Tenant A admin context valid. | 2026-03-01T01:12:52Z | `evidence/api/test-19-live-20260301T011252Z-01-auth-me-admin.*` |
| 2 | GET | `https://api.valensjewelry.com/api/auth/me` | `Authorization: Bearer <member_token>` | `200` | Tenant A member context valid. | 2026-03-01T01:12:53Z | `evidence/api/test-19-live-20260301T011252Z-02-auth-me-member.*` |
| 3 | POST | `https://api.valensjewelry.com/api/auth/signup` | Fresh Tenant B signup payload (`company_name` included) | `201` | Tenant B admin token issued for isolated probes. | 2026-03-01T01:12:54Z | `evidence/api/test-19-live-20260301T011252Z-03-signup-tenantb.*` |
| 4 | GET | `https://api.valensjewelry.com/api/users/me/digest-settings` | `Authorization: Bearer <tenant_b_token>` | `200` | Initial digest settings observed: `digest_enabled=true`, `digest_recipients=null`. | 2026-03-01T01:12:54Z | `evidence/api/test-19-live-20260301T011252Z-05-digest-settings-get-initial.*` |
| 5 | PATCH | `https://api.valensjewelry.com/api/users/me/digest-settings` | `{"digest_enabled":false,"digest_recipients":"maromaher54@gmail.com,wave3acc+20260228T213251Z@example.com"}` | `200` | Update accepted. | 2026-03-01T01:12:55Z | `evidence/api/test-19-live-20260301T011252Z-07-digest-settings-patch-disable-custom-recipients.*` |
| 6 | GET | `https://api.valensjewelry.com/api/users/me/digest-settings` | `Authorization: Bearer <tenant_b_token>` | `200` | Updated values persisted (`digest_enabled=false`, recipients string present). | 2026-03-01T01:12:55Z | `evidence/api/test-19-live-20260301T011252Z-08-digest-settings-get-after-disable.*` |
| 7 | PATCH | `https://api.valensjewelry.com/api/users/me/digest-settings` | `{"digest_enabled":true,"digest_recipients":""}` | `200` | Clear+enable accepted (`digest_recipients` normalized to `null`). | 2026-03-01T01:12:56Z | `evidence/api/test-19-live-20260301T011252Z-09-digest-settings-patch-enable-clear.*` |
| 8 | PATCH | same as #7 (repeat) | Same payload as #7 | `200` | Idempotent retry returned stable response body. | 2026-03-01T01:12:57Z | `evidence/api/test-19-live-20260301T011252Z-11-digest-settings-patch-enable-clear-repeat.*` |
| 9 | PATCH | `https://api.valensjewelry.com/api/users/me/digest-settings` | `Authorization: Bearer <member_token>`, `{"digest_enabled":false}` | `403` | Member blocked (`Only admins can update digest settings`). | 2026-03-01T01:12:57Z | `evidence/api/test-19-live-20260301T011252Z-12-digest-settings-patch-member-forbidden.*` |
| 10 | PATCH | same as #9 | No auth header | `401` | Unauthenticated request blocked. | 2026-03-01T01:12:57Z | `evidence/api/test-19-live-20260301T011252Z-13-digest-settings-patch-no-auth.*` |
| 11 | GET | `https://api.valensjewelry.com/api/users/me/slack-settings` | `Authorization: Bearer <tenant_b_token>` | `200` | Initial Slack settings observed: `slack_webhook_configured=false`, `slack_digest_enabled=false`. | 2026-03-01T01:12:55Z | `evidence/api/test-19-live-20260301T011252Z-06-slack-settings-get-initial.*` |
| 12 | PATCH | `https://api.valensjewelry.com/api/users/me/slack-settings` | `{"slack_webhook_url":"https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX","slack_digest_enabled":true}` | `200` | Valid hooks-shape URL accepted; configured flag true on subsequent GET. | 2026-03-01T01:12:59Z | `evidence/api/test-19-live-20260301T011252Z-16-slack-settings-patch-valid-hooks-url.*`, `...-17-slack-settings-get-after-valid-hooks.*` |
| 13 | PATCH | same endpoint | `{"slack_webhook_url":"https://example.com/webhook","slack_digest_enabled":true}` | `200` | **Unexpected:** non-Slack domain accepted (expected reject). | 2026-03-01T01:12:59Z | `evidence/api/test-19-live-20260301T011252Z-18-slack-settings-patch-ssrf-examplecom.*` |
| 14 | PATCH | same endpoint | `{"slack_webhook_url":"http://169.254.169.254/latest/meta-data/","slack_digest_enabled":true}` | `200` | **Unexpected:** metadata IP URL accepted (expected reject). | 2026-03-01T01:13:00Z | `evidence/api/test-19-live-20260301T011252Z-19-slack-settings-patch-ssrf-metadata-ip.*` |
| 15 | PATCH | same endpoint | `{"slack_webhook_url":"https://hooks.slack.com.evil.example/services/T000/B000/ZZZZ","slack_digest_enabled":true}` | `200` | **Unexpected:** hooks-lookalike domain accepted (expected reject). | 2026-03-01T01:13:00Z | `evidence/api/test-19-live-20260301T011252Z-20-slack-settings-patch-ssrf-lookalike-domain.*` |
| 16 | PATCH | same endpoint | `{"slack_webhook_url":"","slack_digest_enabled":false}` | `200` | Cleanup applied; webhook cleared and digest disabled. | 2026-03-01T01:13:01Z | `evidence/api/test-19-live-20260301T011252Z-22-slack-settings-patch-clear-and-disable.*` |
| 17 | GET | same endpoint | `Authorization: Bearer <tenant_b_token>` | `200` | Post-cleanup persisted (`slack_webhook_configured=false`, `slack_digest_enabled=false`). | 2026-03-01T01:13:01Z | `evidence/api/test-19-live-20260301T011252Z-23-slack-settings-get-after-clear.*` |
| 18 | PATCH | same endpoint | `Authorization: Bearer <member_token>`, `{"slack_digest_enabled":true}` | `403` | Member blocked (`Only admins can update Slack settings`). | 2026-03-01T01:13:02Z | `evidence/api/test-19-live-20260301T011252Z-24-slack-settings-patch-member-forbidden.*` |
| 19 | PATCH | same endpoint | No auth header | `401` | Unauthenticated PATCH blocked. | 2026-03-01T01:13:02Z | `evidence/api/test-19-live-20260301T011252Z-25-slack-settings-patch-no-auth.*` |
| 20 | GET | `https://api.valensjewelry.com/api/users/me/slack-settings` | No auth header | `401` | Unauthenticated GET blocked. | 2026-03-01T01:13:02Z | `evidence/api/test-19-live-20260301T011252Z-26-slack-settings-get-no-auth.*` |
| 21 | GET | `https://api.valensjewelry.com/api/users/me/digest-settings` | No auth header | `401` | Unauthenticated GET blocked. | 2026-03-01T01:13:03Z | `evidence/api/test-19-live-20260301T011252Z-27-digest-settings-get-no-auth.*` |
| 22 | N/A | Contract/persistence/security summaries | N/A | N/A | Digest persistence checks all true; webhook security checks failed expected rejects (`400`) for all unsafe probes. | 2026-03-01T01:13:04Z | `evidence/api/test-19-live-20260301T011252Z-28-contract-summary.json`, `...-29-digest-persistence-check.json`, `...-30-slack-webhook-security-check.json`, `...-99-context-summary.txt` |
| 23 | N/A | Post-deploy rerun summary | N/A | N/A | Fresh rerun passed full contract: unsafe webhook probes now rejected (`400`) while positive path, persistence, and auth-boundary checks remained green. | 2026-03-01T01:57:56Z | `evidence/api/test-19-rerun-20260301T015756Z-28-contract-summary.json`, `...-29-digest-persistence-check.json`, `...-30-slack-webhook-security-check.json`, `...-99-context-summary.txt` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/settings?tab=notifications` (no auth session) | Route responds deterministically without frontend crash | `200` HTML response shell; no route-level crash observed from no-auth probe | `evidence/ui/test-19-live-20260301T011252Z-ui-01-settings-notifications-no-auth.*` |
| `GET https://dev.valensjewelry.com/settings?tab=notifications` (no auth session, rerun) | Route responds deterministically without frontend crash | `200` HTML response shell; no route-level crash observed in rerun | `evidence/ui/test-19-rerun-20260301T015756Z-ui-01-settings-notifications-no-auth.*` |

## Assertions

- Positive path: PASS. Both settings endpoints exist and support `GET/PATCH`; digest and Slack toggle updates persisted on immediate reload in both initial and rerun Tenant B probes.
- Negative path: PASS (post-deploy rerun). Webhook security probes rejected unsafe URLs with `400` (`https://example.com/webhook`, `http://169.254.169.254/latest/meta-data/`, `https://hooks.slack.com.evil.example/...`), while valid `hooks.slack.com/services/...` remained accepted (`200`).
- Auth boundary: PASS for endpoint protection. Member PATCH requests returned `403`; no-auth GET/PATCH requests returned `401` across digest and Slack settings in both runs.
- Contract shape: PASS for observed schema. Digest endpoint returned `{digest_enabled,digest_recipients}`; Slack endpoint returned `{slack_webhook_configured,slack_digest_enabled}` and did not expose raw webhook URL.
- Idempotency/retry: PASS for digest PATCH retry. Repeat `{"digest_enabled":true,"digest_recipients":""}` returned the same `200` response body.
- Auditability: PASS. Full request/status/headers/body/timestamp artifacts captured for all probes and summarized in derived contract/security check files.

## Tracker Updates

- Primary tracker section/row: Section 3 row #4 and Section 4 row #18 (both closed by post-deploy rerun evidence); Section 1 rows #4/#5 remained fixed.
- Tracker section hint: Section 1 and Section 3.
- Section 8 checkbox impact: `T19-4` now checked from rerun evidence; `T19` medium checklist item remains complete for persistence behavior.
- Section 9 changelog update needed: Yes (record post-deploy rerun closure for Section 3 #4 / Section 4 #18 / Section 8 `T19-4`).

## Notes

- Evidence prefix: `test-19-live-20260301T011252Z-*`.
- Rerun evidence prefix: `test-19-rerun-20260301T015756Z-*`.
- Tenant B was intentionally used for mutable Slack webhook URL probes so live Tenant A webhook secrets were not overwritten during security testing.
- No product code changes were made during this live validation run.
