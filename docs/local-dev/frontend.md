# Frontend Development

## Runtime Location

Frontend app is in `/Users/marcomaher/AWS Security Autopilot/frontend`.

## Configure API URL

`frontend/.env`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

## Auth and Request Model

- Browser mode uses cookie credentials (`credentials: include`) and CSRF header on unsafe methods.
- Bearer token compatibility exists for scripted/API flows.

## Common Backend Endpoints Called by Frontend

- Auth: `/api/auth/signup`, `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`
- Accounts: `/api/aws/accounts`
- Findings/actions: `/api/findings`, `/api/actions`
- Remediation: `/api/remediation-runs`
- Settings routes: `/settings?tab=account|team|organization|notifications|integrations|governance|remediation-defaults|exports-compliance|baseline-report`
- Reporting routes: `/exports` (entry page only), `/baseline-report` (redirects to Settings)
- Exports/report APIs: `/api/exports`, `/api/baseline-report`, `/api/control-mappings`
- Users/settings APIs: `/api/users`, `/api/users/me/digest-settings`, `/api/users/me/slack-settings`, `/api/users/me/governance-settings`, `/api/users/me/remediation-settings`, `/api/integrations/settings`

## Related

- [Backend development](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/backend.md)
- [Environment setup](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/environment.md)
