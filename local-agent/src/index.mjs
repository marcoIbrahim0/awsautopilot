import { createServer } from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import pty from 'node-pty';
import { WebSocketServer } from 'ws';

const HOST = '127.0.0.1';
const PORT = Number(process.env.AGENT_PORT || 0);
const ALLOWED_ORIGIN = (process.env.AGENT_ALLOWED_ORIGIN || '').trim();
const ALLOW_BROWSER = process.env.AGENT_ALLOW_BROWSER === '1';
const IDLE_TIMEOUT_MS = Number(process.env.AGENT_SESSION_IDLE_TIMEOUT_SEC || 1800) * 1000;
const TICKET_TTL_MS = Number(process.env.AGENT_WS_TICKET_TTL_SEC || 30) * 1000;
const AUDIT_ENABLED = process.env.AGENT_AUDIT_LOG === '1';
const APP_DIR = getAppDir();
const STATE_FILE = path.join(APP_DIR, 'state.json');
const TOKEN_FILE = path.join(APP_DIR, 'agent_token');
const AUDIT_FILE = path.join(APP_DIR, 'audit.log');
const ALLOWED_WORKDIRS = parseAllowedWorkdirs();

fs.mkdirSync(APP_DIR, { recursive: true, mode: 0o700 });
const AGENT_TOKEN = loadOrCreateToken();

const sessions = new Map();

function nowIso() {
  return new Date().toISOString();
}

function audit(event, details = {}) {
  if (!AUDIT_ENABLED) return;
  const payload = {
    ts: nowIso(),
    event,
    details,
  };
  fs.appendFileSync(AUDIT_FILE, `${JSON.stringify(payload)}\n`, { mode: 0o600 });
}

function getAppDir() {
  const configHome = process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config');
  if (process.platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Application Support', 'AWS Security Autopilot Local Agent');
  }
  if (process.platform === 'win32') {
    return path.join(process.env.APPDATA || configHome, 'AWS Security Autopilot Local Agent');
  }
  return path.join(configHome, 'aws-security-autopilot-local-agent');
}

function parseAllowedWorkdirs() {
  const raw = (process.env.AGENT_ALLOWED_WORKDIRS || os.homedir()).trim();
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .map((p) => path.resolve(p));
}

function loadOrCreateToken() {
  if (process.env.AGENT_AUTH_TOKEN && process.env.AGENT_AUTH_TOKEN.trim()) {
    return process.env.AGENT_AUTH_TOKEN.trim();
  }
  if (fs.existsSync(TOKEN_FILE)) {
    return fs.readFileSync(TOKEN_FILE, 'utf8').trim();
  }
  const token = crypto.randomBytes(32).toString('hex');
  fs.writeFileSync(TOKEN_FILE, `${token}\n`, { mode: 0o600 });
  return token;
}

function isLoopback(remoteAddress) {
  if (!remoteAddress) return false;
  return (
    remoteAddress === '127.0.0.1' ||
    remoteAddress === '::1' ||
    remoteAddress === '::ffff:127.0.0.1'
  );
}

function enforceOrigin(req, res = null) {
  const origin = req.headers.origin || '';
  if (!ALLOW_BROWSER && origin) {
    if (res) {
      res.writeHead(403, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'browser_clients_disabled' }));
    }
    return false;
  }
  if (!ALLOWED_ORIGIN) return true;
  const allowed = origin === ALLOWED_ORIGIN;
  if (!allowed && res) {
    res.writeHead(403, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'forbidden_origin' }));
  }
  return allowed;
}

function enforceHttpAuth(req, res) {
  if (!isLoopback(req.socket.remoteAddress)) {
    res.writeHead(403, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'loopback_only' }));
    return false;
  }
  if (!enforceOrigin(req, res)) {
    return false;
  }
  const auth = req.headers.authorization || '';
  const expected = `Bearer ${AGENT_TOKEN}`;
  if (auth !== expected) {
    res.writeHead(401, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'unauthorized' }));
    return false;
  }
  return true;
}

function sendJson(res, code, payload) {
  res.writeHead(code, {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-store',
  });
  res.end(JSON.stringify(payload));
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => {
      data += chunk;
      if (data.length > 2 * 1024 * 1024) {
        reject(new Error('payload_too_large'));
      }
    });
    req.on('end', () => {
      if (!data) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(data));
      } catch {
        reject(new Error('invalid_json'));
      }
    });
    req.on('error', reject);
  });
}

function sanitizeEnv(userEnv = {}) {
  const base = {
    TERM: 'xterm-256color',
    COLORTERM: 'truecolor',
    LANG: process.env.LANG || 'en_US.UTF-8',
  };
  const allow = new Set([
    'AWS_PROFILE',
    'AWS_REGION',
    'AWS_DEFAULT_REGION',
    'AWS_PAGER',
    'PAGER',
    'LESS',
    'NO_COLOR',
    'EDITOR',
    'VISUAL',
  ]);
  for (const [k, v] of Object.entries(userEnv || {})) {
    if (allow.has(k) && typeof v === 'string') {
      base[k] = v;
    }
  }
  return base;
}

function defaultShell() {
  if (process.platform === 'win32') {
    return process.env.COMSPEC || 'powershell.exe';
  }
  return process.env.SHELL || '/bin/zsh';
}

function isCwdAllowed(inputCwd) {
  const candidate = path.resolve(inputCwd || os.homedir());
  for (const allowedRoot of ALLOWED_WORKDIRS) {
    if (candidate === allowedRoot || candidate.startsWith(`${allowedRoot}${path.sep}`)) {
      return candidate;
    }
  }
  return null;
}

function createSession(body) {
  const cols = Math.max(20, Math.min(400, Number(body.cols || 120)));
  const rows = Math.max(5, Math.min(200, Number(body.rows || 36)));
  const cwd = isCwdAllowed(body.cwd || os.homedir());
  if (!cwd) {
    throw new Error('cwd_not_allowed');
  }

  const shell = typeof body.shell === 'string' && body.shell.trim() ? body.shell.trim() : defaultShell();
  const args = Array.isArray(body.args) ? body.args.filter((a) => typeof a === 'string') : [];

  const ptyProcess = pty.spawn(shell, args, {
    name: 'xterm-256color',
    cols,
    rows,
    cwd,
    env: {
      ...process.env,
      ...sanitizeEnv(body.env),
    },
    useConpty: process.platform === 'win32',
  });

  const id = crypto.randomUUID();
  const session = {
    id,
    ptyProcess,
    cwd,
    shell,
    createdAt: Date.now(),
    lastActivityAt: Date.now(),
    exitCode: null,
    closed: false,
    sockets: new Set(),
    tickets: new Map(),
    buffer: [],
  };

  ptyProcess.onData((chunk) => {
    session.lastActivityAt = Date.now();
    if (session.buffer.length > 2000) {
      session.buffer.shift();
    }
    session.buffer.push(chunk);
    const payload = JSON.stringify({ type: 'output', data: chunk });
    for (const ws of session.sockets) {
      if (ws.readyState === ws.OPEN) ws.send(payload);
    }
  });

  ptyProcess.onExit(({ exitCode, signal }) => {
    session.closed = true;
    session.exitCode = exitCode;
    session.lastActivityAt = Date.now();
    const payload = JSON.stringify({ type: 'exit', exitCode, signal });
    for (const ws of session.sockets) {
      if (ws.readyState === ws.OPEN) ws.send(payload);
      ws.close();
    }
    audit('session_exit', { id, exitCode, signal });
  });

  sessions.set(id, session);
  audit('session_create', { id, cwd, shell });
  return session;
}

function getSession(id) {
  const session = sessions.get(id);
  if (!session) {
    throw new Error('session_not_found');
  }
  return session;
}

function issueTicket(session) {
  const ticket = crypto.randomBytes(24).toString('base64url');
  session.tickets.set(ticket, Date.now() + TICKET_TTL_MS);
  return ticket;
}

function consumeTicket(session, ticket) {
  const exp = session.tickets.get(ticket);
  if (!exp) return false;
  session.tickets.delete(ticket);
  if (Date.now() > exp) return false;
  return true;
}

function destroySession(session, reason = 'terminated') {
  if (!session.closed) {
    try {
      session.ptyProcess.kill();
    } catch {
      // no-op
    }
  }
  for (const ws of session.sockets) {
    try {
      ws.close();
    } catch {
      // no-op
    }
  }
  sessions.delete(session.id);
  audit('session_destroy', { id: session.id, reason });
}

const server = createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    sendJson(res, 200, { ok: true, ts: nowIso() });
    return;
  }

  if (!enforceHttpAuth(req, res)) {
    return;
  }

  try {
    const url = new URL(req.url, `http://${HOST}`);

    if (req.method === 'POST' && url.pathname === '/v1/sessions') {
      const body = await readJsonBody(req);
      const session = createSession(body);
      sendJson(res, 201, {
        id: session.id,
        cwd: session.cwd,
        shell: session.shell,
        created_at: new Date(session.createdAt).toISOString(),
        idle_timeout_sec: IDLE_TIMEOUT_MS / 1000,
      });
      return;
    }

    const match = url.pathname.match(/^\/v1\/sessions\/([0-9a-fA-F-]+)(?:\/(ticket|resize))?$/);
    if (match) {
      const [, sessionId, action] = match;
      const session = getSession(sessionId);

      if (req.method === 'GET' && !action) {
        sendJson(res, 200, {
          id: session.id,
          cwd: session.cwd,
          shell: session.shell,
          closed: session.closed,
          exit_code: session.exitCode,
          attached_clients: session.sockets.size,
          created_at: new Date(session.createdAt).toISOString(),
          last_activity_at: new Date(session.lastActivityAt).toISOString(),
        });
        return;
      }

      if (req.method === 'DELETE' && !action) {
        destroySession(session, 'api_delete');
        sendJson(res, 204, {});
        return;
      }

      if (req.method === 'POST' && action === 'ticket') {
        const ticket = issueTicket(session);
        sendJson(res, 200, {
          ticket,
          expires_in_sec: TICKET_TTL_MS / 1000,
          ws_path: `/v1/sessions/${session.id}/stream?ticket=${ticket}`,
        });
        return;
      }

      if (req.method === 'POST' && action === 'resize') {
        const body = await readJsonBody(req);
        const cols = Math.max(20, Math.min(400, Number(body.cols || 120)));
        const rows = Math.max(5, Math.min(200, Number(body.rows || 36)));
        session.ptyProcess.resize(cols, rows);
        session.lastActivityAt = Date.now();
        sendJson(res, 200, { ok: true, cols, rows });
        return;
      }
    }

    sendJson(res, 404, { error: 'not_found' });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (message === 'session_not_found') {
      sendJson(res, 404, { error: message });
      return;
    }
    if (message === 'cwd_not_allowed') {
      sendJson(res, 400, { error: message, allowed_roots: ALLOWED_WORKDIRS });
      return;
    }
    if (message === 'invalid_json' || message === 'payload_too_large') {
      sendJson(res, 400, { error: message });
      return;
    }
    sendJson(res, 500, { error: 'internal_error', detail: message });
  }
});

const wss = new WebSocketServer({ noServer: true });

server.on('upgrade', (req, socket, head) => {
  try {
    if (!isLoopback(req.socket.remoteAddress)) {
      socket.destroy();
      return;
    }
    if (!enforceOrigin(req)) {
      socket.destroy();
      return;
    }
    const url = new URL(req.url, `http://${HOST}`);
    const match = url.pathname.match(/^\/v1\/sessions\/([0-9a-fA-F-]+)\/stream$/);
    if (!match) {
      socket.destroy();
      return;
    }
    const session = getSession(match[1]);
    const ticket = url.searchParams.get('ticket') || '';
    if (!consumeTicket(session, ticket)) {
      socket.destroy();
      return;
    }

    wss.handleUpgrade(req, socket, head, (ws) => {
      ws.session = session;
      wss.emit('connection', ws, req);
    });
  } catch {
    socket.destroy();
  }
});

wss.on('connection', (ws) => {
  const session = ws.session;
  session.sockets.add(ws);
  session.lastActivityAt = Date.now();

  ws.send(JSON.stringify({
    type: 'session',
    id: session.id,
    cwd: session.cwd,
    shell: session.shell,
    created_at: new Date(session.createdAt).toISOString(),
  }));

  if (session.buffer.length > 0) {
    const replay = session.buffer.join('');
    ws.send(JSON.stringify({ type: 'output', data: replay }));
  }

  ws.on('message', (raw) => {
    try {
      const message = JSON.parse(String(raw));
      session.lastActivityAt = Date.now();
      if (message.type === 'input' && typeof message.data === 'string') {
        session.ptyProcess.write(message.data);
        return;
      }
      if (message.type === 'resize') {
        const cols = Math.max(20, Math.min(400, Number(message.cols || 120)));
        const rows = Math.max(5, Math.min(200, Number(message.rows || 36)));
        session.ptyProcess.resize(cols, rows);
        return;
      }
      if (message.type === 'detach') {
        ws.close();
      }
    } catch {
      // ignore malformed ws message
    }
  });

  ws.on('close', () => {
    session.sockets.delete(ws);
    session.lastActivityAt = Date.now();
  });
});

setInterval(() => {
  const now = Date.now();
  for (const session of sessions.values()) {
    for (const [ticket, exp] of session.tickets) {
      if (now > exp) session.tickets.delete(ticket);
    }
    if (session.closed) {
      sessions.delete(session.id);
      continue;
    }
    const idleMs = now - session.lastActivityAt;
    if (session.sockets.size === 0 && idleMs > IDLE_TIMEOUT_MS) {
      destroySession(session, 'idle_timeout');
    }
  }
}, 15000);

server.listen(PORT, HOST, () => {
  const address = server.address();
  const actualPort = typeof address === 'object' && address ? address.port : PORT;
  const state = {
    host: HOST,
    port: actualPort,
    started_at: nowIso(),
    browser_clients_enabled: ALLOW_BROWSER,
    allowed_origin: ALLOWED_ORIGIN || null,
    allowed_workdirs: ALLOWED_WORKDIRS,
  };
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), { mode: 0o600 });
  console.log(`[local-agent] listening on http://${HOST}:${actualPort}`);
  console.log(`[local-agent] state file: ${STATE_FILE}`);
  if (!process.env.AGENT_AUTH_TOKEN) {
    console.log(`[local-agent] token file: ${TOKEN_FILE}`);
  }
});

process.on('SIGTERM', () => {
  for (const session of sessions.values()) {
    destroySession(session, 'shutdown');
  }
  process.exit(0);
});

process.on('SIGINT', () => {
  for (const session of sessions.values()) {
    destroySession(session, 'shutdown');
  }
  process.exit(0);
});
