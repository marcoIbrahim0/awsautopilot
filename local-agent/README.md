# AWS Security Autopilot Local Agent (MVP)

Local-only PTY execution service for embedded terminal UIs.

## Run locally
```bash
cd /Users/marcomaher/AWS Security Autopilot/local-agent
npm install
AGENT_ALLOW_BROWSER=0 npm start
```

## Security defaults
- Listens on `127.0.0.1` only
- Browser clients are blocked by default (`Origin` header denied unless `AGENT_ALLOW_BROWSER=1`)
- Requires bearer token for HTTP API
- WebSocket attach requires short-lived one-time ticket
- Optional strict origin check via `AGENT_ALLOWED_ORIGIN`
- Restricts working directories via `AGENT_ALLOWED_WORKDIRS`

## Runtime files
- macOS: `~/Library/Application Support/AWS Security Autopilot Local Agent/`
- Linux: `~/.config/aws-security-autopilot-local-agent/`
- Windows: `%APPDATA%\\AWS Security Autopilot Local Agent\\`

Generated files:
- `agent_token` (0600)
- `state.json` (contains host/port)
- `audit.log` (if `AGENT_AUDIT_LOG=1`)

See `/Users/marcomaher/AWS Security Autopilot/docs/local-terminal-agent-mvp.md` for architecture, threat model, service install, and UI wiring.
