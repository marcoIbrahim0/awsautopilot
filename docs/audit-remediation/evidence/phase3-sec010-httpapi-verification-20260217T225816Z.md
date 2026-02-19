# SEC-010 HTTP API Verification and Architecture-Change Closure (2026-02-17T23:46:32Z)

## Objective
Resolve SEC-010 through architecture change (not risk acceptance) by moving production edge traffic to a WAF-supported front door and re-verifying objective controls.

## Authoritative Inputs
- `OWNER_ARN=arn:aws:iam::029037611564:user/AutoPilotAdmin`
- `OWNER_NAME=AutoPilotAdmin`
- `TIMESTAMP_UTC=2026-02-17T23:46:32Z`
- `SEC010_DECISION=Require Architecture Change`

## Baseline Blocked Finding (Superseded)
Direct AWS WAF association to the HTTP API stage ARN format remained blocked in this environment:
`arn:aws:apigateway:eu-north-1::/apis/g1frb5hhfg/stages/$default`.

Objective artifacts:
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-sec010-httpapi-verify-20260217T225816Z.txt`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-security-20260217T224836Z.md`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-security-20260217T224836Z.json`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-sec010-evidence-collect-20260217T224831Z.txt`

## Architecture Change Applied (Production Front Door)
Minimum architecture change implemented:
1. Production edge traffic moved to WAF-supported API Gateway REST stage:
   - REST API ID: `brplhu7801`
   - Stage: `prod`
   - Stage ARN: `arn:aws:apigateway:eu-north-1::/restapis/brplhu7801/stages/prod`
2. REST front door configured with proxy routes (`ANY /` and `ANY /{proxy+}`) to Lambda `security-autopilot-dev-api`.
3. Front-door health invocation succeeded (`status=200`, body contains `{"status":"ok","app":"AWS Security Autopilot"}`).

Objective artifact:
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-sec010-architecture-change-success-20260217T234632Z.txt`

## WAF Association Verification (Production Path)
1. `wafv2 list-resources-for-web-acl` includes production stage ARN:
   - `arn:aws:apigateway:eu-north-1::/restapis/brplhu7801/stages/prod`
2. `apigateway get-stage` for `brplhu7801/prod` returns matching `webAclArn`.
3. Front-door health invocation remains successful after association.

Objective artifact:
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-sec010-waf-production-association-success-20260217T234632Z.txt`

## Alarm/Notification Path Verification
1. CloudWatch alarms `security-autopilot-edge-web-acl-blocked-requests` and `security-autopilot-edge-web-acl-rate-limit-triggered` are in `OK` with validation recovery marker `SEC-010 architecture change validation recovery 20260217T234632Z`.
2. Alarm actions remain wired to SNS topic `arn:aws:sns:eu-north-1:029037611564:security-autopilot-alarms`.
3. SNS topic subscription remains present (email endpoint `marcoibrahim11@outlook.com`).

Objective artifact:
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-sec010-alarm-notification-success-20260217T234632Z.txt`

## Closure Decision
- Security owner: `AutoPilotAdmin` (`arn:aws:iam::029037611564:user/AutoPilotAdmin`)
- Decision timestamp (UTC): `2026-02-17T23:46:32Z`
- Decision: `Require Architecture Change`
- SEC-010 status: **Resolved**
- Resolution path: **Architecture change applied and objectively re-verified** (no risk acceptance used).

## Attached Decision Artifact

- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-sec010-decision-20260217T234632Z.md`

## Cross-Links
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/phase3-security-closure-checklist.md`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/evidence/phase3-phase4-closure-index-20260217T195458Z.md`
- `/Users/marcomaher/AWS Security Autopilot/docs/audit-remediation/03-security-plan.md`
