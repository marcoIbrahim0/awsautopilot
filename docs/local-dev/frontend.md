# Frontend Development

This guide covers frontend development for AWS Security Autopilot. The frontend is a React/Next.js application that communicates with the FastAPI backend.

## Overview

The frontend application provides:
- User authentication (login, signup, invite acceptance)
- AWS account onboarding and management
- Findings and actions views
- Remediation approvals and exceptions
- Evidence exports and baseline reports
- Settings (team management, notifications, digest/Slack)

## Frontend Location

The frontend codebase may be:
- **In a separate repository** — Check with your team for the frontend repo location
- **In this repository** — Look for a `frontend/` directory (may not be present)

## Connecting Frontend to Local Backend

### Environment Variables

The frontend needs to know the backend API URL. Configure canonical public vars in `frontend/.env` (optionally override locally in `frontend/.env.local`):

```bash
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# Or if using ngrok for AWS service testing
NEXT_PUBLIC_API_URL=https://your-ngrok-url.ngrok-free.app
```

Canonical env model used by this project:
- Backend runtime: `/Users/marcomaher/AWS Security Autopilot/backend/.env`
- Worker runtime: `/Users/marcomaher/AWS Security Autopilot/backend/workers/.env`
- Frontend public vars: `/Users/marcomaher/AWS Security Autopilot/frontend/.env`
- Deploy/ops scripts: `/Users/marcomaher/AWS Security Autopilot/config/.env.ops`
- Root `/Users/marcomaher/AWS Security Autopilot/.env` is backup-only and commented out.

### CORS Configuration

Ensure backend CORS allows frontend origin. In `backend/.env`:

```bash
CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
```

### Authentication

The frontend uses JWT tokens for authentication:
- **Token storage**: HTTP-only cookies or localStorage (check frontend implementation)
- **Token refresh**: May use refresh tokens (check frontend auth implementation)
- **CSRF protection**: If using cookies, frontend sends `X-CSRF-Token` header

---

## Running the Frontend

### Prerequisites

- **Node.js** 18+ and **npm** or **yarn**
- Frontend repository cloned (if separate)

### Development Server

```bash
# Navigate to frontend directory
cd frontend  # Or wherever frontend code is

# Install dependencies
npm install
# Or: yarn install

# Run development server
npm run dev
# Or: yarn dev
```

The frontend will be available at:
- **HTTP**: http://localhost:3000

### Hot Reload

The Next.js dev server supports hot reload:
- Code changes automatically refresh the browser
- API changes require backend restart (not frontend)

---

## Frontend Architecture

### Pages/Routes

Typical Next.js pages structure:

- `/` — Landing page or dashboard
- `/login` — Login page
- `/signup` — Signup page
- `/accept-invite` — Invite acceptance page
- `/onboarding` — 5-step onboarding wizard
- `/accounts` — AWS account management
- `/findings` — Findings view
- `/actions` — Actions/Top Risks view
- `/settings` — Settings (Team, Organization, Notifications)

### API Integration

The frontend makes HTTP requests to backend API:

```typescript
// Example API call
const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/findings`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
});
const data = await response.json();
```

### Authentication Context

The frontend likely uses React Context for auth state:

```typescript
// Example AuthContext usage
const { user, token, login, logout } = useAuth();
```

---

## Development Workflow

### 1. Start Backend

```bash
# Terminal 1: Start backend
uvicorn backend.main:app --reload
```

### 2. Start Frontend

```bash
# Terminal 2: Start frontend
cd frontend
npm run dev
```

### 3. Test End-to-End

1. Open http://localhost:3000
2. Sign up or log in
3. Complete onboarding wizard
4. Connect AWS account
5. View findings and actions

---

## Frontend-Backend Integration

### API Endpoints

The frontend calls backend endpoints:

- **Auth**: `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`
- **Accounts**: `GET /api/aws-accounts`, `POST /api/aws-accounts`
- **Findings**: `GET /api/findings`
- **Actions**: `GET /api/actions`, `POST /api/actions/compute`
- **Remediation**: `POST /api/remediation-runs`, `POST /api/remediation-runs/{id}/approve`
- **Exports**: `POST /api/exports`, `GET /api/exports`
- **Users**: `GET /api/users`, `POST /api/users/invite`

See [API Reference](../api/README.md) for complete endpoint documentation.

### Error Handling

The frontend should handle:
- **401 Unauthorized** — Redirect to login
- **403 Forbidden** — Show permission error
- **404 Not Found** — Show not found page
- **500 Server Error** — Show error message

### Loading States

Show loading indicators for:
- API requests
- Long-running operations (ingestion, exports)
- Page navigation

---

## Testing Frontend Locally

### Manual Testing

1. **Test authentication flow**:
   - Sign up → Verify email (if required)
   - Log in → Verify token storage
   - Log out → Verify token cleared

2. **Test onboarding**:
   - Complete 5-step wizard
   - Verify External ID generated
   - Connect AWS account
   - Trigger ingestion

3. **Test core features**:
   - View findings
   - View actions
   - Create exceptions
   - Approve remediations
   - Generate exports

### Browser DevTools

Use browser DevTools to:
- **Network tab**: Inspect API requests/responses
- **Console**: Check for JavaScript errors
- **Application tab**: Inspect cookies/localStorage

### Mocking Backend (Optional)

For frontend-only development, consider:
- **MSW (Mock Service Worker)**: Mock API responses
- **JSON Server**: Simple REST API mock

---

## Common Issues

### CORS Errors

**Error**: `Access to fetch at 'http://localhost:8000/api/...' from origin 'http://localhost:3000' has been blocked by CORS policy`

**Solution**: Add frontend origin to backend `CORS_ORIGINS`:
```bash
CORS_ORIGINS="http://localhost:3000"
```

### Authentication Errors

**Error**: `401 Unauthorized`

**Solution**:
- Check token is sent in `Authorization` header
- Verify token hasn't expired
- Check backend `JWT_SECRET` matches (if regenerated)

### API Connection Errors

**Error**: `Failed to fetch` or network errors

**Solution**:
- Verify backend is running on correct port
- Check `NEXT_PUBLIC_API_URL` matches backend URL
- Verify no firewall blocking localhost connections

---

## Production Considerations

For production deployment:
- **Build**: `npm run build` (Next.js production build)
- **Deploy**: Deploy to Vercel, Netlify, or similar
- **Environment**: Set `NEXT_PUBLIC_API_URL` to production API URL
- **SSL**: Use HTTPS for production (required for cookies with `Secure` flag)

---

## Next Steps

- **[Backend Development](backend.md)** — Run the API locally
- **[API Reference](../api/README.md)** — Complete API documentation
- **[Customer Guide](../customer-guide/README.md)** — User-facing documentation

---

## See Also

- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev/)
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)
