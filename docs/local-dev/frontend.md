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
- Exports/report: `/api/exports`, `/api/baseline-report`
- Users/settings: `/api/users`, `/api/users/me/digest-settings`, `/api/users/me/slack-settings`

## Related

- [Backend development](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/backend.md)
- [Environment setup](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/environment.md)
