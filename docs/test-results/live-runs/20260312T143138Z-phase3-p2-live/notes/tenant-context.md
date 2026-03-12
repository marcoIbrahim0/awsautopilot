# Tenant Context

- Tenant ID: `9f7616d8-af04-43ca-99cd-713625357b70`
- Tenant name: `Valens`
- Operator user ID: `7c43e0b3-6e98-43af-826f-f4eeaa5af674`
- Operator email: `marco.ibrahim@ocypheris.com`
- Connected accounts:
  - AWS account record `537fee33-429d-4b06-9080-7ee490293355`
  - AWS account ID `696505809372`
  - Status `validated`
  - `role_read_arn` present
  - `role_write_arn` absent
- Findings discovered on live: `7`
- Actions discovered on live: `6`
- Threat-intel-bearing findings/actions discovered on live: `0`
- Auth path used:
  - Fresh browser session reached authenticated `https://ocypheris.com/findings`
  - `GET /api/auth/me` returned the same operator identity for API evidence capture

Supporting evidence:
- `../evidence/api/01-auth-me.body.json`
- `../evidence/api/02-accounts.body.json`
- `../evidence/api/03-findings.body.json`
- `../evidence/api/04-actions.body.json`
- `../evidence/ui/01-login-success.png`
