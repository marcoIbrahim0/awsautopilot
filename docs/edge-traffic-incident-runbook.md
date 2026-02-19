# Edge Traffic Incident Runbook

Use this runbook when WAF blocked-traffic or rate-limit alarms fire for public API traffic.

Primary IaC:
- `/Users/marcomaher/AWS Security Autopilot/infrastructure/cloudformation/edge-protection.yaml`

Related architecture:
- `/Users/marcomaher/AWS Security Autopilot/docs/edge-protection-architecture.md`

## Trigger Conditions

- `*-blocked-requests` alarm is `ALARM`.
- `*-rate-limit-triggered` alarm is `ALARM`.
- API error rates increase with corresponding WAF blocks.

## 1. Confirm Alarm Context

```bash
aws cloudwatch describe-alarms \
  --alarm-names <web-acl-name>-blocked-requests <web-acl-name>-rate-limit-triggered
```

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/WAFV2 \
  --metric-name BlockedRequests \
  --start-time <iso-start> \
  --end-time <iso-end> \
  --period 300 \
  --statistics Sum \
  --dimensions Name=WebACL,Value=<web-acl-name> Name=Region,Value=<region-or-global> Name=Rule,Value=ALL
```

## 2. Identify Offending Sources

Capture sampled WAF requests:

```bash
aws wafv2 get-sampled-requests \
  --scope REGIONAL \
  --web-acl-arn <web-acl-arn> \
  --rule-metric-name IPAddressRateLimit \
  --max-items 100 \
  --time-window StartTime=<iso-start>,EndTime=<iso-end>
```

If `Scope=CLOUDFRONT`, run the same command with `--scope CLOUDFRONT` in `us-east-1`.

## 3. Mitigate

Options (choose least disruptive first):

1. Temporary source block (known abusive CIDR)
- Add CIDR to a block rule/IP set in the Web ACL and deploy change.

2. Tighten rate limits
- Reduce `RateLimitRequestsPer5Min` and redeploy stack.

3. Restrict ingress surface during active attack
- Enable `EnableIpv4AllowList=true` with approved CIDRs.

## 4. Validate Recovery

- Confirm WAF alarms move from `ALARM` to `OK`.
- Confirm application availability and latency recover.
- Confirm no false-positive lockout for trusted traffic.

## 5. Post-Incident Actions

- Record root cause, mitigations, and blast radius.
- Review whether thresholds/managed rules need tuning.
- If allow-list was enabled temporarily, schedule controlled rollback or permanent policy update.

## Dashboard Links (Populate Per Environment)

- CloudWatch WAF dashboard: `<dashboard-url>`
- Alarm detail view: `<alarm-url>`
- Incident ticket: `<ticket-url>`
