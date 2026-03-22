# Local Execution Without a Browser (Desktop-Only MVP)

## Goal
Provide an interactive terminal inside product UX, but **do not allow browser clients** to connect to the local agent.

## Default decision
- Browser access: **disabled**
- Local transport: localhost TCP for now, but browser requests are rejected (`Origin` header blocked)
- Intended client: native desktop app (Electron/Tauri/Swift/.NET) acting as trusted local UI

## Why this is safer
- Prevents arbitrary websites from hitting localhost endpoints.
- Avoids token exposure in browser runtime/storage.
- Keeps execution path local and user-scoped.

## Architecture
- Local background agent service per OS:
  - macOS: LaunchAgent (user context, required for `~/.aws` and SSO cache)
  - Windows: Windows Service (prefer dedicated low-privilege user account)
  - Linux: systemd user service
- Agent exposes HTTP + WebSocket API and PTY sessions.
- Desktop app calls API directly and renders terminal output in embedded terminal component.

## Implemented controls
- Bind `127.0.0.1` only.
- HTTP bearer token required.
- WebSocket attach requires one-time short-lived ticket.
- Browser requests blocked by default (`AGENT_ALLOW_BROWSER=0`).
- Working directory allowlist (`AGENT_ALLOWED_WORKDIRS`).
- Detached-session idle timeout cleanup.
- Optional audit metadata logs only.

## API (unchanged)
- `GET /health`
- `POST /v1/sessions`
- `GET /v1/sessions/:id`
- `POST /v1/sessions/:id/ticket`
- `POST /v1/sessions/:id/resize`
- `DELETE /v1/sessions/:id`
- `WS /v1/sessions/:id/stream?ticket=...`

## Service context decision
### macOS: LaunchAgent vs LaunchDaemon
Use **LaunchAgent**.
- Needed for user AWS profile and SSO cache.
- LaunchDaemon is system/root scoped and not suitable for user shell context.

## Threat model focus
1. Malicious webpage hitting localhost.
- Mitigation: browser requests rejected by default.

2. Local process probing localhost.
- Mitigation: bearer auth + one-time WS ticket + loopback binding.

3. Compromised desktop app process.
- Mitigation: token rotation/revocation, least-privilege service account, command restrictions.

## AWS CLI behavior
Interactive AWS CLI remains supported via PTY (`aws sso login`, MFA prompts, pagers).
- Prefer user’s existing `~/.aws/config` and SSO cache.
- Do not send long-lived AWS credentials from SaaS to local agent.

## Local dev workflow
```bash
cd /Users/marcomaher/AWS Security Autopilot/local-agent
npm install
AGENT_ALLOW_BROWSER=0 AGENT_AUDIT_LOG=1 npm start
```

State file:
- macOS: `~/Library/Application Support/AWS Security Autopilot Local Agent/state.json`
- Linux: `~/.config/aws-security-autopilot-local-agent/state.json`
- Windows: `%APPDATA%\\AWS Security Autopilot Local Agent\\state.json`

## Packaging guidance (high-level)
- macOS: signed/notarized pkg with LaunchAgent install.
- Windows: signed MSI/EXE installing service with low-privilege account.
- Linux: deb/rpm with systemd user service unit.

## Production hardening checklist
- [ ] Move token to OS keychain/credential manager.
- [ ] Add explicit local pairing flow and revocation.
- [ ] Add command policy (allowlist/denylist) mode.
- [ ] Add per-session resource limits and runtime caps.
- [ ] Add optional transcript redaction if logs are enabled.
- [ ] Add signed auto-update channel.
