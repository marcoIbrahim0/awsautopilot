# Secrets Lifecycle

This page summarizes the current secret surfaces that matter for buyer trust review.

## Secret Matrix

| Secret surface | Purpose | Storage | Rotation owner | Rotation path | Retention / revoke note |
|---|---|---|---|---|---|
| `JWT_SECRET` | Sign user auth JWTs | AWS Secrets Manager secret id pattern `${NAME_PREFIX}/JWT_SECRET`, then injected into runtime env during deploy | SaaS operator | Update the Secrets Manager value, redeploy runtime, invalidate old sessions as needed | Long-lived until rotated; rotation changes auth signing boundary |
| `BUNDLE_REPORTING_TOKEN_SECRET` | Sign customer-run grouped bundle reporting tokens | AWS Secrets Manager secret id pattern `${NAME_PREFIX}/BUNDLE_REPORTING_TOKEN_SECRET`, then injected into runtime env during deploy | SaaS operator | Update the Secrets Manager value and redeploy runtime | Separate from `JWT_SECRET`; rotation invalidates outstanding bundle-report tokens |
| `CONTROL_PLANE_EVENTS_SECRET` | Authenticate internal control-plane endpoints and the scheduler fallback secret path | AWS Secrets Manager secret id pattern `${NAME_PREFIX}/CONTROL_PLANE_EVENTS_SECRET`, then injected into runtime env during deploy | SaaS operator | Update the Secrets Manager value, redeploy runtime, update any callers that use the shared secret | Rotate if internal secret exposure is suspected |
| `OPENAI_API_KEY` | Authorize the Help Hub true-LLM assistant against OpenAI | AWS Secrets Manager secret id `security-autopilot-dev/OPENAI_API_KEY`, then injected into runtime env during deploy | SaaS operator | Update the Secrets Manager value, redeploy runtime, and revalidate `/api/help/assistant/query` | Rotation affects only new Help Hub assistant requests; existing persisted chat rows remain intact |
| `DIGEST_CRON_SECRET` | Authenticate the weekly digest scheduler endpoint | Runtime secret/config per deployment environment | SaaS operator | Update deployment secret value and redeploy runtime | Endpoint remains deny-closed when unset |
| Tenant control-plane token | Auth for tenant EventBridge forwarder `X-Control-Plane-Token` header | Hashed in the tenant row; plaintext is one-time reveal only | Tenant admin / SaaS admin assisting tenant setup | `POST /api/auth/control-plane-token/rotate` and `POST /api/auth/control-plane-token/revoke` | Revoke immediately disables the current token without waiting for a full runtime redeploy |

## Current Rules

- Bundle reporting tokens must use `BUNDLE_REPORTING_TOKEN_SECRET`; there is no `JWT_SECRET` fallback.
- The deploy path can resolve `JWT_SECRET`, `BUNDLE_REPORTING_TOKEN_SECRET`, and `CONTROL_PLANE_EVENTS_SECRET` from Secrets Manager when they are absent from `config/.env.ops`.
- The serverless Help Hub deploy path resolves `OPENAI_API_KEY` from `OPENAI_API_KEY_SECRET_ID` instead of storing the plaintext key in `config/.env.ops`.
- Tenant control-plane tokens are never returned again after creation or rotation; the UI/API only expose fingerprint and active/revoked state after that point.

## Supporting Docs

- [Secrets & configuration management](/Users/marcomaher/AWS%20Security%20Autopilot/docs/deployment/secrets-config.md)
- [Control-plane event monitoring](/Users/marcomaher/AWS%20Security%20Autopilot/docs/control-plane-event-monitoring.md)
