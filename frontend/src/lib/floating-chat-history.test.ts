import {
  clearFloatingChatSessions,
  FLOATING_CHAT_ACTIVE_THREAD_KEY,
  FLOATING_CHAT_HISTORY_WINDOW_MS,
  FLOATING_CHAT_SESSIONS_KEY,
  getFloatingChatActiveThreadId,
  readFloatingChatIndex,
  removeFloatingChatSession,
  setFloatingChatActiveThreadId,
  upsertFloatingChatSession,
} from '@/lib/floating-chat-history';

describe('floating chat history', () => {
  beforeEach(() => {
    localStorage.removeItem(FLOATING_CHAT_SESSIONS_KEY);
    localStorage.removeItem(FLOATING_CHAT_ACTIVE_THREAD_KEY);
  });

  it('stores multiple recent chats and sorts by latest activity', () => {
    const base = Date.UTC(2026, 2, 23, 12, 0, 0);
    upsertFloatingChatSession({ thread_id: 'thread-1', preview: 'First question' }, base);
    upsertFloatingChatSession({ thread_id: 'thread-2', preview: 'Second question' }, base + 1_000);

    const index = readFloatingChatIndex(base + 2_000);

    expect(index.sessions.map((item) => item.thread_id)).toEqual(['thread-2', 'thread-1']);
    expect(index.sessions[0]?.preview).toBe('Second question');
  });

  it('refreshes expiry on activity and prunes expired sessions after 6 hours', () => {
    const base = Date.UTC(2026, 2, 23, 12, 0, 0);
    upsertFloatingChatSession({ thread_id: 'thread-1', preview: 'First question' }, base);
    upsertFloatingChatSession(
      { thread_id: 'thread-1', preview: 'Follow-up question' },
      base + 60_000,
    );

    expect(readFloatingChatIndex(base + FLOATING_CHAT_HISTORY_WINDOW_MS - 1).sessions).toHaveLength(1);
    expect(
      readFloatingChatIndex(base + 60_000 + FLOATING_CHAT_HISTORY_WINDOW_MS + 1).sessions,
    ).toHaveLength(0);
  });

  it('restores the active thread only when it still exists and is not expired', () => {
    const base = Date.UTC(2026, 2, 23, 12, 0, 0);
    upsertFloatingChatSession({ thread_id: 'thread-1', preview: 'First question' }, base);
    upsertFloatingChatSession({ thread_id: 'thread-2', preview: 'Second question' }, base + 1_000);
    setFloatingChatActiveThreadId('thread-1');

    expect(getFloatingChatActiveThreadId(base + 2_000)).toBe('thread-1');

    removeFloatingChatSession('thread-1', base + 3_000);

    expect(getFloatingChatActiveThreadId(base + 4_000)).toBe('thread-2');
    expect(localStorage.getItem(FLOATING_CHAT_ACTIVE_THREAD_KEY)).toBe('thread-2');
  });

  it('clears both the active pointer and stored sessions', () => {
    upsertFloatingChatSession({ thread_id: 'thread-1', preview: 'First question' });
    setFloatingChatActiveThreadId('thread-1');

    clearFloatingChatSessions();

    expect(localStorage.getItem(FLOATING_CHAT_SESSIONS_KEY)).toBeNull();
    expect(localStorage.getItem(FLOATING_CHAT_ACTIVE_THREAD_KEY)).toBeNull();
  });
});
