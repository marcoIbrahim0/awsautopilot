# Edge Protection Architecture

This document defines the Phase 3 (`SEC-010`) edge-defense baseline for public Security Autopilot API traffic.

## Public Exposure Path

1. Internet clients reach the public API entry point (API Gateway stage or ALB).
2. AWS WAF Web ACL evaluates every request before it reaches backend services.
3. Allowed traffic proceeds to application routing.
4. Blocked traffic is counted in `AWS/WAFV2` metrics and alarms.

## Enforced Edge Controls

The IaC baseline is implemented in:
- `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/edge-protection.yaml`

Required controls:
- Managed WAF rules:
  - `AWSManagedRulesCommonRuleSet`
  - `AWSManagedRulesKnownBadInputsRuleSet`
- Source-IP rate limiting:
  - Rule `IPAddressRateLimit`
  - Configurable threshold (`RateLimitRequestsPer5Min`)
- Optional explicit IPv4 allow-list mode:
  - `EnableIpv4AllowList=true`
  - `AllowedIpv4Cidrs` configured with approved admin/office/VPN CIDRs
- CloudWatch alarms:
  - General blocked-request surge alarm
  - Rate-limit trigger alarm

## Attachment Model

The template supports either or both:
- API Gateway stage association (`ApiGatewayStageArn`)
- Application Load Balancer association (`ApplicationLoadBalancerArn`)

Only one edge path should be active per environment unless explicitly required.

## Browser Security Alignment (`SEC-008`)

Browser session protections are layered with edge controls:
- Auth session is delivered by `HttpOnly` cookie (`access_token`) and CSRF cookie/header pairing.
- Frontend API requests use cookie-based credentials and CSRF headers for unsafe methods.
- CSP and browser hardening headers are emitted by Next.js config.

### XSS Threat Assumptions

- `HttpOnly` cookies remove direct JavaScript read access to bearer tokens.
- CSRF defenses do not mitigate in-origin XSS payloads; output encoding and input handling remain mandatory.
- CSP is configured to reduce script injection blast radius, but is defense-in-depth rather than a standalone control.
- Any confirmed XSS finding is treated as a security incident even if token exfiltration is blocked.

## Dashboard and Alert Baseline

Minimum dashboard widgets:
- `AWS/WAFV2 BlockedRequests (Rule=ALL)`
- `AWS/WAFV2 BlockedRequests (Rule=IPAddressRateLimit)`
- `AWS/WAFV2 AllowedRequests`

Alarm routing:
- Alarm SNS topic configured via `AlarmTopicArn`.
- Alerts feed on-call paging and incident tracking.

## Operational Assumptions

- `Scope=REGIONAL` is the default for API Gateway/ALB deployments.
- `Scope=CLOUDFRONT` is used only when the API is fronted by CloudFront.
- Allow-list mode is only enabled when source IP ownership and rotation process are documented.
- Rate-limit thresholds are tuned from observed baseline request rates and revisited after major product launches.
