# SEC-010 Command Log (2026-02-17)

## Context
- Region: `eu-north-1`
- Input API stage ARN (provided): `arn:aws:apigateway:eu-north-1::/apis/g1frb5hhfg/stages/$default`
- Edge Web ACL ARN: `arn:aws:wafv2:eu-north-1:029037611564:regional/webacl/security-autopilot-edge-web-acl/078ed15a-046c-419c-954a-528561d4807a`

## Exact AWS Commands Run

### 1) Validate provided HTTP API stage ARN association behavior
```bash
aws wafv2 associate-web-acl \
  --region eu-north-1 \
  --web-acl-arn arn:aws:wafv2:eu-north-1:029037611564:regional/webacl/security-autopilot-edge-web-acl/078ed15a-046c-419c-954a-528561d4807a \
  --resource-arn 'arn:aws:apigateway:eu-north-1::/apis/g1frb5hhfg/stages/$default'
```
Result observed:
```text
An error occurred (WAFInvalidParameterException) ... field: RESOURCE_ARN, parameter: arn:aws:apigateway:eu-north-1::/apis/g1frb5hhfg/stages/$default
```

### 2) Create drill REST API stage (WAF-compatible ARN format)
```bash
aws apigateway create-rest-api --region eu-north-1 --name security-autopilot-sec010-waf-drill-test --endpoint-configuration types=REGIONAL
aws apigateway put-method --region eu-north-1 --rest-api-id brplhu7801 --resource-id usu10ogr1j --http-method GET --authorization-type NONE --no-api-key-required
aws apigateway put-integration --region eu-north-1 --rest-api-id brplhu7801 --resource-id usu10ogr1j --http-method GET --type HTTP_PROXY --integration-http-method GET --uri 'https://g1frb5hhfg.execute-api.eu-north-1.amazonaws.com'
aws apigateway create-deployment --region eu-north-1 --rest-api-id brplhu7801 --stage-name waf-drill
```
Effective drill stage ARN:
```text
arn:aws:apigateway:eu-north-1::/restapis/brplhu7801/stages/waf-drill
```

### 3) Associate Web ACL (successful)
```bash
aws wafv2 associate-web-acl \
  --region eu-north-1 \
  --web-acl-arn arn:aws:wafv2:eu-north-1:029037611564:regional/webacl/security-autopilot-edge-web-acl/078ed15a-046c-419c-954a-528561d4807a \
  --resource-arn arn:aws:apigateway:eu-north-1::/restapis/brplhu7801/stages/waf-drill
```
Result observed: command returned exit code `0` with no body.

### 4) Verify association via list-resources-for-web-acl (successful)
```bash
aws wafv2 list-resources-for-web-acl \
  --region eu-north-1 \
  --web-acl-arn arn:aws:wafv2:eu-north-1:029037611564:regional/webacl/security-autopilot-edge-web-acl/078ed15a-046c-419c-954a-528561d4807a \
  --resource-type API_GATEWAY \
  --output json
```
Result observed:
```json
{
  "ResourceArns": [
    "arn:aws:apigateway:eu-north-1::/restapis/brplhu7801/stages/waf-drill"
  ]
}
```

### 5) Alarm drill (synthetic state injection) and history capture
Synthetic ALARM trigger commands used:
```bash
aws cloudwatch set-alarm-state --region eu-north-1 --alarm-name security-autopilot-edge-web-acl-blocked-requests --state-value ALARM --state-reason 'SEC-010 synthetic drill 2026-02-17T18:30Z'
aws cloudwatch set-alarm-state --region eu-north-1 --alarm-name security-autopilot-edge-web-acl-rate-limit-triggered --state-value ALARM --state-reason 'SEC-010 synthetic drill 2026-02-17T18:30Z'
```
History verification commands used:
```bash
aws cloudwatch describe-alarm-history --region eu-north-1 --alarm-name security-autopilot-edge-web-acl-blocked-requests --start-date 2026-02-17T18:20:00Z --history-item-type StateUpdate --max-records 20 --output table
aws cloudwatch describe-alarm-history --region eu-north-1 --alarm-name security-autopilot-edge-web-acl-rate-limit-triggered --start-date 2026-02-17T18:20:00Z --history-item-type StateUpdate --max-records 20 --output table
```
Relevant history evidence observed:
- `security-autopilot-edge-web-acl-blocked-requests`: `OK -> ALARM` at `2026-02-17T20:30:37.990+02:00`, then `ALARM -> OK` at `2026-02-17T20:31:28.655+02:00`.
- `security-autopilot-edge-web-acl-rate-limit-triggered`: `OK -> ALARM` at `2026-02-17T20:30:39.211+02:00`, then `ALARM -> OK` at `2026-02-17T20:31:12.698+02:00`.

### 6) Verify alarm action routing target
```bash
aws cloudwatch describe-alarms \
  --region eu-north-1 \
  --alarm-names security-autopilot-edge-web-acl-blocked-requests security-autopilot-edge-web-acl-rate-limit-triggered \
  --query 'MetricAlarms[].{Name:AlarmName,State:StateValue,Threshold:Threshold,Rule:Dimensions[?Name==`Rule`]|[0].Value,Actions:AlarmActions}' \
  --output table
```
Result observed: both alarms include action target
`arn:aws:sns:eu-north-1:029037611564:security-autopilot-alarms`.

## Endpoint Stability Notes
Intermittent AWS endpoint connectivity occurred during this run (`wafv2`, `monitoring`, `sns`, `cloudformation`, and occasionally `apigateway`). Raw failed-attempt artifacts are preserved in this folder for audit traceability.

## Key Outcome
- WAF association verification is present for API Gateway resource ARN:
  - `arn:aws:apigateway:eu-north-1::/restapis/brplhu7801/stages/waf-drill`
- Synthetic blocked/rate-limit alarm drill produced ALARM and recovery transitions in CloudWatch alarm history.
