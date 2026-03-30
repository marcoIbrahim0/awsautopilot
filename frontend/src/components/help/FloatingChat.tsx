'use client';

import { useEffect, useRef, useState } from 'react';
import { X, Send, RefreshCw, History, ChevronLeft } from 'lucide-react';
import { usePathname } from 'next/navigation';

import { Button } from '@/components/ui/Button';
import { useAuth } from '@/contexts/AuthContext';
import {
  approveHelpAssistantCase,
  getErrorMessage,
  getHelpAssistantThread,
  HelpAssistantLiveLookup,
  HelpAssistantThread,
  HelpAssistantTurn,
  queryHelpAssistant,
} from '@/lib/api';
import {
  FLOATING_CHAT_HISTORY_WINDOW_MS,
  FLOATING_CHAT_USAGE_KEY,
  FloatingChatSession,
  getFloatingChatActiveThreadId,
  readFloatingChatIndex,
  removeFloatingChatSession,
  setFloatingChatActiveThreadId,
  upsertFloatingChatSession,
} from '@/lib/floating-chat-history';

const MAX_CHATS = 5;
const RATE_LIMIT_HOURS = 6;

function getUsage(): number[] {
  try {
    const usage = JSON.parse(localStorage.getItem(FLOATING_CHAT_USAGE_KEY) || '[]');
    return Array.isArray(usage) ? usage : [];
  } catch {
    return [];
  }
}

function persistUsage(usage: number[]): void {
  localStorage.setItem(FLOATING_CHAT_USAGE_KEY, JSON.stringify(usage));
}

function formatSessionTime(value: string): string {
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function emptyThread(threadId: string): HelpAssistantThread {
  return { thread_id: threadId, current_path: null, turns: [] };
}

function cloneWithTurn(
  thread: HelpAssistantThread | null,
  threadId: string,
  turn: HelpAssistantTurn,
  currentPath: string,
): HelpAssistantThread {
  const base = thread?.thread_id === threadId ? thread : emptyThread(threadId);
  return {
    thread_id: threadId,
    current_path: currentPath,
    turns: [...base.turns, turn],
  };
}

function usageWindowMessage(oldest: number): string {
  const availableAt = new Date(oldest + RATE_LIMIT_HOURS * 60 * 60 * 1000);
  return `You've reached the limit of ${MAX_CHATS} messages per ${RATE_LIMIT_HOURS} hours. You can send another message at ${availableAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.`;
}

function recentPreview(session: FloatingChatSession): string {
  return session.preview.trim() || 'Untitled chat';
}

function AssistantGlyph({ className = 'h-6 w-6' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="assistant-obelisk-right" x1="32" y1="4" x2="46" y2="60" gradientUnits="userSpaceOnUse">
          <stop stopColor="#3A96FF" />
          <stop offset="1" stopColor="#0B71FF" />
        </linearGradient>
        <linearGradient id="assistant-obelisk-left" x1="15" y1="8" x2="31" y2="60" gradientUnits="userSpaceOnUse">
          <stop stopColor="#2945B5" />
          <stop offset="1" stopColor="#213D9E" />
        </linearGradient>
      </defs>
      <path d="M32 4 19 16l11-5 2-1.2V4Z" fill="url(#assistant-obelisk-left)" />
      <path d="m32 4 13 12-11-5-2-1.2V4Z" fill="url(#assistant-obelisk-right)" />
      <path d="M16.5 60 22 18l10-5.2V60H16.5Z" fill="url(#assistant-obelisk-left)" />
      <path d="M32 60V12.8L42 18l5.5 42H32Z" fill="url(#assistant-obelisk-right)" />
      <path d="m22 18 10-5.2L42 18l-10-2.8L22 18Z" fill="#081F63" />
      <path d="M32 12.8V60" stroke="#081F63" strokeWidth="1.8" strokeOpacity="0.9" />
    </svg>
  );
}

function LiveLookupCard({
  liveLookup,
  isLoading,
  onConfirm,
  onChooseAccount,
}: {
  liveLookup: HelpAssistantLiveLookup | null;
  isLoading: boolean;
  onConfirm: (accountId: string | null) => void;
  onChooseAccount: (accountId: string) => void;
}) {
  if (!liveLookup) return null;
  if (liveLookup.status === 'pending_confirmation') {
    return (
      <div className="mt-3 rounded-2xl border border-warning/35 bg-warning/10 p-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-warning">Live IAM check available</p>
        <p className="mt-2 text-xs leading-6 text-text/85">{liveLookup.message}</p>
        <div className="mt-3">
          <Button size="sm" onClick={() => onConfirm(liveLookup.account_id)} disabled={isLoading}>
            Run live IAM check
          </Button>
        </div>
      </div>
    );
  }
  if (liveLookup.status === 'account_selection_required' && liveLookup.candidate_accounts.length) {
    return (
      <div className="mt-3 rounded-2xl border border-warning/35 bg-warning/10 p-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-warning">Select an account</p>
        <p className="mt-2 text-xs leading-6 text-text/85">{liveLookup.message}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {liveLookup.candidate_accounts.map((candidate) => (
            <Button key={candidate.account_id} size="sm" variant="secondary" onClick={() => onChooseAccount(candidate.account_id)}>
              {candidate.account_id}
            </Button>
          ))}
        </div>
      </div>
    );
  }
  if (liveLookup.status === 'executed' && liveLookup.observations.length) {
    return (
      <div className="mt-3 rounded-2xl border border-accent/25 bg-accent/8 p-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted">Live IAM observations</p>
        <div className="mt-3 space-y-2">
          {liveLookup.observations.map((observation) => (
            <div key={`${observation.title}-${observation.summary}`} className="rounded-2xl border border-border/40 bg-[var(--bg)] p-3">
              <p className="text-xs font-semibold text-text">{observation.title}</p>
              <p className="mt-1 text-xs leading-6 text-text/85">{observation.summary}</p>
              {observation.details.length ? (
                <p className="mt-1 text-[11px] leading-5 text-muted">{observation.details.join(' | ')}</p>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (['disabled', 'failed'].includes(liveLookup.status) && liveLookup.message) {
    return (
      <div className="mt-3 rounded-2xl border border-warning/35 bg-warning/10 p-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-warning">Live lookup</p>
        <p className="mt-2 text-xs leading-6 text-text/85">{liveLookup.message}</p>
      </div>
    );
  }
  return null;
}

export function FloatingChat() {
  const pathname = usePathname();
  const { isAuthenticated } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [isOpen, setIsOpen] = useState(false);
  const [showRecentChats, setShowRecentChats] = useState(false);
  const [sessions, setSessions] = useState<FloatingChatSession[]>([]);
  const [activeThreadId, setActiveThreadIdState] = useState<string | null>(null);
  const [threadsById, setThreadsById] = useState<Record<string, HelpAssistantThread>>({});
  const [question, setQuestion] = useState('');
  const [activeQuestion, setActiveQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rateLimitMessage, setRateLimitMessage] = useState<string | null>(null);

  const activeThread = activeThreadId ? threadsById[activeThreadId] ?? null : null;
  const activeTurn = activeThread?.turns[activeThread.turns.length - 1] ?? null;

  function syncSessions(now: number = Date.now()): FloatingChatSession[] {
    const nextSessions = readFloatingChatIndex(now).sessions;
    setSessions(nextSessions);
    const nextActive = getFloatingChatActiveThreadId(now);
    setActiveThreadIdState(nextActive);
    return nextSessions;
  }

  function checkRateLimit(): boolean {
    const now = Date.now();
    const usage = getUsage().filter((time) => now - time < RATE_LIMIT_HOURS * 60 * 60 * 1000);
    if (usage.length !== getUsage().length) persistUsage(usage);
    if (usage.length >= MAX_CHATS) {
      setRateLimitMessage(usageWindowMessage(usage[0]));
      return false;
    }
    setRateLimitMessage(null);
    return true;
  }

  async function loadThread(threadId: string): Promise<void> {
    const existing = threadsById[threadId];
    if (existing) {
      setActiveThreadIdState(threadId);
      setFloatingChatActiveThreadId(threadId);
      return;
    }
    const payload = await getHelpAssistantThread(threadId);
    setThreadsById((current) => ({ ...current, [threadId]: payload }));
    setActiveThreadIdState(threadId);
    setFloatingChatActiveThreadId(threadId);
  }

  useEffect(() => {
    if (messagesEndRef.current) messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [activeThread?.turns, activeQuestion, isLoading, showRecentChats]);

  useEffect(() => {
    if (!isAuthenticated) return;
    syncSessions();
    checkRateLimit();
    const interval = window.setInterval(() => {
      syncSessions();
      checkRateLimit();
    }, 60_000);
    return () => window.clearInterval(interval);
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated || !activeThreadId) return;
    if (threadsById[activeThreadId]) return;
    getHelpAssistantThread(activeThreadId)
      .then((payload) => {
        setThreadsById((current) => ({ ...current, [activeThreadId]: payload }));
      })
      .catch(() => {
        removeFloatingChatSession(activeThreadId);
        const nextSessions = syncSessions();
        setThreadsById((current) => {
          const next = { ...current };
          delete next[activeThreadId];
          return next;
        });
        if (!nextSessions.length) setShowRecentChats(false);
      });
  }, [activeThreadId, isAuthenticated, threadsById]);

  if (!isAuthenticated) return null;

  async function handleSend(
    event?: React.FormEvent,
    options?: { confirmLiveLookup?: boolean; accountIdOverride?: string | null; presetQuestion?: string },
  ) {
    if (event) event.preventDefault();
    const currentQuestion = (options?.presetQuestion ?? question).trim();
    if (!currentQuestion || isLoading) return;
    if (!checkRateLimit()) return;

    setQuestion('');
    setActiveQuestion(currentQuestion);
    setError(null);
    setIsLoading(true);
    setShowRecentChats(false);

    const usage = getUsage().filter((time) => Date.now() - time < RATE_LIMIT_HOURS * 60 * 60 * 1000);
    usage.push(Date.now());
    persistUsage(usage);

    try {
      const response = await queryHelpAssistant({
        question: currentQuestion,
        thread_id: activeThreadId,
        current_path: pathname,
        account_id: options?.accountIdOverride ?? undefined,
        request_human: false,
        confirm_live_lookup: options?.confirmLiveLookup ?? false,
      });
      const nextTurn: HelpAssistantTurn = {
        interaction_id: response.interaction_id,
        question: currentQuestion,
        answer: response.answer,
        confidence: response.confidence,
        suggested_case: response.suggested_case,
        citations: response.citations,
        follow_up_questions: response.follow_up_questions,
        context_gaps: response.context_gaps,
        helpful: null,
        feedback_text: null,
        created_at: new Date().toISOString(),
        escalated_case_id: response.escalated_case_id,
        live_lookup: response.live_lookup,
      };
      const nextThread = cloneWithTurn(activeThread, response.thread_id, nextTurn, pathname);
      setThreadsById((current) => ({ ...current, [response.thread_id]: nextThread }));
      setActiveThreadIdState(response.thread_id);
      setFloatingChatActiveThreadId(response.thread_id);
      setSessions(upsertFloatingChatSession({ thread_id: response.thread_id, preview: currentQuestion }).sessions);
    } catch (err) {
      setError(getErrorMessage(err));
      setQuestion(currentQuestion);
      const usageRollback = getUsage();
      usageRollback.pop();
      persistUsage(usageRollback);
    } finally {
      setIsLoading(false);
      setActiveQuestion('');
    }
  }

  function handleNewChat(): void {
    setActiveThreadIdState(null);
    setFloatingChatActiveThreadId(null);
    setActiveQuestion('');
    setQuestion('');
    setError(null);
    setShowRecentChats(false);
  }

  async function handleApproveCase(interactionId: string): Promise<void> {
    if (isLoading) return;
    setError(null);
    setIsLoading(true);
    try {
      const response = await approveHelpAssistantCase(interactionId);
      if (!activeThreadId) return;
      setThreadsById((current) => {
        const thread = current[activeThreadId];
        if (!thread) return current;
        return {
          ...current,
          [activeThreadId]: {
            ...thread,
            turns: thread.turns.map((turn) =>
              turn.interaction_id === response.interaction_id
                ? { ...turn, escalated_case_id: response.escalated_case_id }
                : turn,
            ),
          },
        };
      });
      if (response.escalated_case_id) {
        window.location.href = `/help?tab=cases&case=${encodeURIComponent(response.escalated_case_id)}&thread=${encodeURIComponent(response.thread_id)}`;
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleOpenRecentChat(threadId: string): Promise<void> {
    setError(null);
    setShowRecentChats(false);
    try {
      await loadThread(threadId);
    } catch (err) {
      setError(getErrorMessage(err));
      removeFloatingChatSession(threadId);
      setSessions(syncSessions());
    }
  }

  function handleRemoveRecentChat(threadId: string): void {
    setSessions(removeFloatingChatSession(threadId).sessions);
    setThreadsById((current) => {
      const next = { ...current };
      delete next[threadId];
      return next;
    });
    if (activeThreadId === threadId) {
      const nextActive = getFloatingChatActiveThreadId();
      setActiveThreadIdState(nextActive);
    }
  }

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className={`fixed bottom-6 right-6 z-50 transition-all duration-200 ${isOpen ? 'pointer-events-none scale-90 opacity-0' : 'scale-100 opacity-100'}`}
        aria-label="Open Ask AI Chat"
      >
        <div className="group relative overflow-hidden rounded-[1.75rem] border border-[#89C7FF]/50 bg-[radial-gradient(circle_at_top_left,_rgba(127,208,255,0.85),_rgba(11,113,255,0.96)_42%,_rgba(9,35,105,1)_100%)] px-4 py-3 text-white shadow-[0_24px_56px_-18px_rgba(7,42,120,0.72)] ring-1 ring-[#0B71FF]/20 transition-transform duration-200 hover:-translate-y-1">
          <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.24),transparent_42%,rgba(255,255,255,0.08)_72%,transparent)]" />
          <div className="absolute -right-4 -top-4 h-16 w-16 rounded-full bg-white/12 blur-xl" />
          <div className="relative flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/25 bg-white/12 shadow-[inset_0_1px_0_rgba(255,255,255,0.2)]">
              <AssistantGlyph className="h-[1.375rem] w-[1.375rem]" />
            </div>
            <div className="hidden sm:block text-left">
              <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/72">Ocypheris</p>
              <p className="text-sm font-semibold">Ask AI</p>
            </div>
          </div>
        </div>
      </button>

      {isOpen ? (
        <div className="fixed bottom-6 right-6 z-50 flex h-[640px] max-h-[85vh] w-[420px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-3xl border border-border/60 bg-[var(--bg)] shadow-[0_24px_60px_-20px_rgba(0,0,0,0.28)]">
          <div className="flex items-center justify-between border-b border-border/40 bg-[var(--card-inset)] px-5 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#89C7FF]/35 bg-[radial-gradient(circle_at_top_left,_rgba(127,208,255,0.24),_rgba(11,113,255,0.14)_48%,_rgba(9,35,105,0.2)_100%)] shadow-[0_18px_36px_-24px_rgba(11,113,255,0.42)]">
                <AssistantGlyph className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-text">Ask AI</h3>
                  <span className="rounded-full border border-[#89C7FF]/35 bg-[#0B71FF]/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#0B71FF]">
                    AI Assistant
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-muted">
                  Temporary floating history lasts {Math.round(FLOATING_CHAT_HISTORY_WINDOW_MS / 3_600_000)} hours.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowRecentChats((current) => !current)}
                className="rounded-full p-2 text-muted transition-colors hover:bg-border/40 hover:text-text"
                title="Recent chats"
              >
                <History className="h-4 w-4" />
              </button>
              <button
                onClick={handleNewChat}
                className="rounded-full p-2 text-muted transition-colors hover:bg-border/40 hover:text-text"
                title="New chat"
              >
                <RefreshCw className="h-4 w-4" />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="rounded-full p-2 text-muted transition-colors hover:bg-border/40 hover:text-text"
                title="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            {showRecentChats ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setShowRecentChats(false)}
                    className="rounded-full p-2 text-muted transition-colors hover:bg-border/40 hover:text-text"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <div>
                    <p className="text-sm font-semibold text-text">Recent chats</p>
                    <p className="text-xs text-muted">Available for the last 6 hours only.</p>
                  </div>
                </div>
                {sessions.length ? (
                  sessions.map((session) => (
                    <div key={session.thread_id} className="rounded-2xl border border-border/50 bg-[var(--card-inset)] p-3">
                      <button type="button" onClick={() => handleOpenRecentChat(session.thread_id)} className="w-full text-left">
                        <p className="text-sm font-semibold text-text">{recentPreview(session)}</p>
                        <p className="mt-1 text-xs text-muted">
                          Updated {formatSessionTime(session.last_updated_at)} | Expires {formatSessionTime(session.expires_at)}
                        </p>
                      </button>
                      <div className="mt-3 flex justify-end">
                        <Button size="sm" variant="secondary" onClick={() => handleRemoveRecentChat(session.thread_id)}>
                          Remove
                        </Button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-border/60 bg-[var(--card-inset)] p-4 text-sm text-muted">
                    No recent floating chats yet.
                  </div>
                )}
              </div>
            ) : !activeThread?.turns.length ? (
              <div className="flex h-full flex-col justify-center text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.5rem] border border-[#89C7FF]/35 bg-[radial-gradient(circle_at_top_left,_rgba(127,208,255,0.2),_rgba(11,113,255,0.12)_48%,_rgba(9,35,105,0.14)_100%)] shadow-[0_18px_44px_-26px_rgba(11,113,255,0.42)]">
                  <AssistantGlyph className="h-8 w-8" />
                </div>
                <p className="mt-4 text-sm font-semibold text-text">How can Ocypheris AI help today?</p>
                <p className="mx-auto mt-2 max-w-[260px] text-xs leading-6 text-muted">
                  Ask questions about findings, AWS accounts, remediation, or Help Hub articles. Recent temporary chats stay here for 6 hours.
                </p>
                {sessions.length ? (
                  <div className="mt-5">
                    <Button variant="secondary" size="sm" onClick={() => setShowRecentChats(true)}>
                      View recent chats
                    </Button>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="space-y-6">
                {activeThread.turns.map((turn) => (
                  <div key={turn.interaction_id} className="space-y-4">
                    <div className="flex justify-end">
                      <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-accent px-4 py-2.5 text-sm text-white shadow-sm">
                        {turn.question}
                      </div>
                    </div>
                    <div className="flex justify-start">
                      <div className="max-w-[88%] rounded-2xl rounded-tl-sm border border-border/50 bg-[var(--card-inset)] px-4 py-3 text-sm text-text/90 shadow-sm">
                        <p className="whitespace-pre-line leading-6">{turn.answer}</p>
                        {!turn.escalated_case_id && turn.suggested_case ? (
                          <div className="mt-3 border-t border-border/40 pt-3">
                            <Button size="sm" variant="secondary" onClick={() => handleApproveCase(turn.interaction_id)} disabled={isLoading}>
                              Open support case
                            </Button>
                          </div>
                        ) : null}
                        <LiveLookupCard
                          liveLookup={turn.live_lookup}
                          isLoading={isLoading}
                          onConfirm={(accountId) => handleSend(undefined, { confirmLiveLookup: true, accountIdOverride: accountId })}
                          onChooseAccount={(accountId) => handleSend(undefined, { accountIdOverride: accountId, presetQuestion: turn.question })}
                        />
                        {turn.context_gaps.length ? (
                          <div className="mt-3 rounded-2xl border border-warning/35 bg-warning/10 p-3">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-warning">Context gaps</p>
                            <p className="mt-2 text-xs leading-6 text-text/85">{turn.context_gaps.join(' ')}</p>
                          </div>
                        ) : null}
                        {turn.citations.length ? (
                          <div className="mt-3 border-t border-border/40 pt-3">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted">Citations</p>
                            <ul className="mt-2 space-y-2">
                              {turn.citations.map((citation) => (
                                <li key={`${turn.interaction_id}-${citation.slug}`} className="rounded-2xl border border-border/40 bg-[var(--bg)] px-3 py-2">
                                  <p className="text-xs font-semibold text-text">{citation.title}</p>
                                  <p className="mt-1 text-[11px] leading-5 text-muted">{citation.summary}</p>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
                {activeTurn?.follow_up_questions.length ? (
                  <div className="rounded-2xl border border-border/50 bg-[var(--card-inset)] p-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted">Suggested follow-ups</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {activeTurn.follow_up_questions.map((followUp) => (
                        <Button key={followUp} variant="secondary" size="sm" onClick={() => setQuestion(followUp)}>
                          {followUp}
                        </Button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            )}

            {activeQuestion && isLoading ? (
              <div className="mt-6 space-y-4">
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-accent px-4 py-2.5 text-sm text-white shadow-sm">
                    {activeQuestion}
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-border/50 bg-[var(--card-inset)] px-4 py-3 text-sm text-text/90 shadow-sm">
                    <div className="flex gap-1">
                      <span className="h-2 w-2 animate-bounce rounded-full bg-accent/60" style={{ animationDelay: '0ms' }} />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-accent/60" style={{ animationDelay: '150ms' }} />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-accent/60" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-border/40 bg-[var(--card-inset)] p-4">
            {error ? <p className="mb-2 text-xs text-danger">{error}</p> : null}
            {rateLimitMessage ? (
              <div className="rounded-xl border border-orange-500/30 bg-orange-500/10 p-3 text-center text-sm font-medium text-orange-400">
                {rateLimitMessage}
              </div>
            ) : (
              <form
                onSubmit={(event) => handleSend(event)}
                className="flex items-end gap-2 rounded-2xl border border-border bg-[var(--input-bg)] p-2 transition-all focus-within:border-accent/55 focus-within:ring-2 focus-within:ring-accent/20"
              >
                <textarea
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="Ask AI a question..."
                  className="max-h-32 min-h-10 w-full resize-none bg-transparent px-3 py-2 text-sm text-text placeholder-muted focus:outline-none"
                  rows={1}
                />
                <Button
                  type="submit"
                  size="sm"
                  variant="accent"
                  isLoading={isLoading}
                  disabled={!question.trim() || isLoading}
                  rightIcon={<Send className="h-4 w-4" />}
                  className="mb-0.5 h-10 min-w-[132px] shrink-0 rounded-xl border-[#7BBEFF] bg-[linear-gradient(135deg,#0B71FF,#0A2F8F)] px-4 text-white shadow-[0_14px_28px_-18px_rgba(11,113,255,0.85)] hover:border-[#9AD8FF] hover:bg-[linear-gradient(135deg,#1284FF,#0A3AA3)] hover:text-white"
                >
                  Send now
                </Button>
              </form>
            )}
            <div className="mt-2 flex items-center justify-between gap-3 text-[10px] text-muted">
              <span>AI can make mistakes. Verify important information.</span>
              <button type="button" onClick={() => setShowRecentChats(true)} className="font-medium text-accent">
                Recent chats
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
