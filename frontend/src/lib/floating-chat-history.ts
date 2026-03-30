export const FLOATING_CHAT_ACTIVE_THREAD_KEY = 'floating_assistant_active_thread_id';
export const FLOATING_CHAT_SESSIONS_KEY = 'floating_assistant_sessions';
export const FLOATING_CHAT_USAGE_KEY = 'floating_assistant_usage';

export const FLOATING_CHAT_HISTORY_WINDOW_MS = 6 * 60 * 60 * 1000;

export interface FloatingChatSession {
  thread_id: string;
  preview: string;
  last_updated_at: string;
  expires_at: string;
}

export interface FloatingChatSessionIndex {
  sessions: FloatingChatSession[];
}

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function parseIndex(raw: string | null): FloatingChatSessionIndex {
  if (!raw) return { sessions: [] };
  try {
    const parsed = JSON.parse(raw) as FloatingChatSessionIndex;
    if (!Array.isArray(parsed.sessions)) return { sessions: [] };
    return {
      sessions: parsed.sessions.filter((item) =>
        Boolean(item?.thread_id && item?.last_updated_at && item?.expires_at),
      ),
    };
  } catch {
    return { sessions: [] };
  }
}

function sortSessions(sessions: FloatingChatSession[]): FloatingChatSession[] {
  return [...sessions].sort(
    (left, right) =>
      new Date(right.last_updated_at).getTime() - new Date(left.last_updated_at).getTime(),
  );
}

export function pruneFloatingChatSessions(
  sessions: FloatingChatSession[],
  now: number = Date.now(),
): FloatingChatSession[] {
  return sortSessions(
    sessions.filter((session) => new Date(session.expires_at).getTime() > now),
  );
}

export function readFloatingChatIndex(now: number = Date.now()): FloatingChatSessionIndex {
  if (!isBrowser()) return { sessions: [] };
  const parsed = parseIndex(window.localStorage.getItem(FLOATING_CHAT_SESSIONS_KEY));
  const sessions = pruneFloatingChatSessions(parsed.sessions, now);
  if (sessions.length !== parsed.sessions.length) {
    writeFloatingChatIndex({ sessions });
  }
  return { sessions };
}

export function writeFloatingChatIndex(index: FloatingChatSessionIndex): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(
    FLOATING_CHAT_SESSIONS_KEY,
    JSON.stringify({ sessions: sortSessions(index.sessions) }),
  );
}

export function upsertFloatingChatSession(
  session: { thread_id: string; preview: string },
  now: number = Date.now(),
): FloatingChatSessionIndex {
  const current = readFloatingChatIndex(now);
  const nextSession: FloatingChatSession = {
    thread_id: session.thread_id,
    preview: session.preview,
    last_updated_at: new Date(now).toISOString(),
    expires_at: new Date(now + FLOATING_CHAT_HISTORY_WINDOW_MS).toISOString(),
  };
  const sessions = pruneFloatingChatSessions(
    [
      nextSession,
      ...current.sessions.filter((item) => item.thread_id !== session.thread_id),
    ],
    now,
  );
  const next = { sessions };
  writeFloatingChatIndex(next);
  return next;
}

export function removeFloatingChatSession(threadId: string, now: number = Date.now()): FloatingChatSessionIndex {
  const current = readFloatingChatIndex(now);
  const activeThreadId = isBrowser()
    ? window.localStorage.getItem(FLOATING_CHAT_ACTIVE_THREAD_KEY)
    : null;
  const next = { sessions: current.sessions.filter((item) => item.thread_id !== threadId) };
  writeFloatingChatIndex(next);
  if (activeThreadId === threadId) {
    setFloatingChatActiveThreadId(next.sessions[0]?.thread_id ?? null);
  }
  return next;
}

export function clearFloatingChatSessions(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(FLOATING_CHAT_SESSIONS_KEY);
  window.localStorage.removeItem(FLOATING_CHAT_ACTIVE_THREAD_KEY);
}

export function getFloatingChatActiveThreadId(now: number = Date.now()): string | null {
  if (!isBrowser()) return null;
  const activeThreadId = window.localStorage.getItem(FLOATING_CHAT_ACTIVE_THREAD_KEY);
  if (!activeThreadId) return readFloatingChatIndex(now).sessions[0]?.thread_id ?? null;
  const sessions = readFloatingChatIndex(now).sessions;
  return sessions.some((item) => item.thread_id === activeThreadId)
    ? activeThreadId
    : sessions[0]?.thread_id ?? null;
}

export function setFloatingChatActiveThreadId(threadId: string | null): void {
  if (!isBrowser()) return;
  if (!threadId) {
    window.localStorage.removeItem(FLOATING_CHAT_ACTIVE_THREAD_KEY);
    return;
  }
  window.localStorage.setItem(FLOATING_CHAT_ACTIVE_THREAD_KEY, threadId);
}
