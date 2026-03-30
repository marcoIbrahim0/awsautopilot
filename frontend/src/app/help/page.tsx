'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { ButtonLink } from '@/components/ui/ButtonLink';
import { Input } from '@/components/ui/Input';
import { useAuth } from '@/contexts/AuthContext';
import {
  DashboardHero,
  DashboardTabButton,
  DashboardTabList,
  dashboardFieldClass,
  remediationInsetClass,
  remediationPanelClass,
} from '@/components/ui/remediation-surface';
import {
  approveHelpAssistantCase,
  createHelpCase,
  getErrorMessage,
  getHelpAssistantThread,
  getHelpCase,
  getHelpCaseAttachmentDownloadUrl,
  getSupportFileDownloadUrl,
  getTenantSupportFiles,
  HelpArticle,
  HelpAssistantThread,
  HelpCase,
  HelpSearchResult,
  listHelpArticles,
  listHelpCases,
  queryHelpAssistant,
  replyToHelpCase,
  searchHelpArticles,
  sendHelpAssistantFeedback,
  SupportFile,
  uploadHelpCaseAttachmentDirect,
} from '@/lib/api';
import { buildHelpHref, HELP_CASE_CATEGORIES, HELP_TABS, normalizeHelpTab } from '@/lib/help';

function articleExcerpt(article: HelpArticle | HelpSearchResult): string {
  return typeof (article as HelpSearchResult).snippet === 'string'
    ? (article as HelpSearchResult).snippet
    : article.summary;
}

function HelpContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const activeTab = normalizeHelpTab(searchParams.get('tab'));
  const from = searchParams.get('from');
  const accountId = searchParams.get('account_id');
  const actionId = searchParams.get('action_id');
  const findingId = searchParams.get('finding_id');
  const caseParam = searchParams.get('case');
  const threadParam = searchParams.get('thread');

  const [articles, setArticles] = useState<HelpArticle[]>([]);
  const [articleQuery, setArticleQuery] = useState('');
  const [searchResults, setSearchResults] = useState<HelpSearchResult[]>([]);
  const [selectedArticleSlug, setSelectedArticleSlug] = useState<string | null>(null);
  const [articlesLoading, setArticlesLoading] = useState(true);
  const [articlesError, setArticlesError] = useState<string | null>(null);

  const [assistantQuestion, setAssistantQuestion] = useState('');
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantError, setAssistantError] = useState<string | null>(null);
  const [assistantThread, setAssistantThread] = useState<HelpAssistantThread | null>(null);
  const [assistantThreadId, setAssistantThreadId] = useState<string | null>(threadParam);
  const [feedbackStatus, setFeedbackStatus] = useState<'idle' | 'saved'>('idle');

  const [cases, setCases] = useState<HelpCase[]>([]);
  const [casesLoading, setCasesLoading] = useState(true);
  const [casesError, setCasesError] = useState<string | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(caseParam);
  const [createSubject, setCreateSubject] = useState('');
  const [createCategory, setCreateCategory] = useState('other');
  const [createPriority, setCreatePriority] = useState('normal');
  const [createBody, setCreateBody] = useState('');
  const [createAttachment, setCreateAttachment] = useState<File | null>(null);
  const [createLoading, setCreateLoading] = useState(false);
  const [replyBody, setReplyBody] = useState('');
  const [replyAttachment, setReplyAttachment] = useState<File | null>(null);
  const [replyLoading, setReplyLoading] = useState(false);

  const [sharedFiles, setSharedFiles] = useState<SupportFile[]>([]);
  const [sharedFilesLoading, setSharedFilesLoading] = useState(false);
  const [sharedFilesError, setSharedFilesError] = useState<string | null>(null);

  const selectedArticle = useMemo(() => {
    const pool = articleQuery.trim() ? searchResults : articles;
    return pool.find((item) => item.slug === selectedArticleSlug) ?? pool[0] ?? null;
  }, [articleQuery, articles, searchResults, selectedArticleSlug]);

  const selectedCase = useMemo(
    () => cases.find((item) => item.id === selectedCaseId) ?? null,
    [cases, selectedCaseId],
  );
  const assistantLatestTurn = useMemo(
    () => assistantThread?.turns[assistantThread.turns.length - 1] ?? null,
    [assistantThread],
  );

  const contextualSummary = useMemo(() => {
    const parts: string[] = [];
    if (from) parts.push(`Route: ${from}`);
    if (accountId) parts.push(`Account: ${accountId}`);
    if (actionId) parts.push(`Action: ${actionId}`);
    if (findingId) parts.push(`Finding: ${findingId}`);
    return parts.join(' | ');
  }, [accountId, actionId, findingId, from]);

  useEffect(() => {
    let active = true;
    listHelpArticles()
      .then((response) => {
        if (!active) return;
        setArticles(response.items);
        setSelectedArticleSlug((current) => current ?? response.items[0]?.slug ?? null);
      })
      .catch((error) => {
        if (!active) return;
        setArticlesError(getErrorMessage(error));
      })
      .finally(() => {
        if (active) setArticlesLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!assistantQuestion.trim()) {
      const base = contextualSummary ? `I need help with ${contextualSummary}.` : 'I need help using AWS Security Autopilot.';
      setAssistantQuestion(base);
    }
    if (!createBody.trim() && contextualSummary) {
      setCreateBody(`Please review this issue.\n\n${contextualSummary}`);
    }
  }, [assistantQuestion, contextualSummary, createBody]);

  useEffect(() => {
    setAssistantThreadId(threadParam);
    if (!threadParam) {
      setAssistantThread(null);
      setFeedbackStatus('idle');
    }
  }, [threadParam]);

  useEffect(() => {
    if (!isAuthenticated || !threadParam) return;
    let active = true;
    getHelpAssistantThread(threadParam)
      .then((payload) => {
        if (!active) return;
        setAssistantThread(payload);
        setAssistantThreadId(payload.thread_id);
      })
      .catch(() => {
        if (!active) return;
        setAssistantThread(null);
      });
    return () => {
      active = false;
    };
  }, [isAuthenticated, threadParam]);

  useEffect(() => {
    if (!isAuthenticated) {
      setCasesLoading(false);
      return;
    }
    let active = true;
    listHelpCases()
      .then((response) => {
        if (!active) return;
        setCases(response.items);
        const nextCaseId = caseParam ?? response.items[0]?.id ?? null;
        setSelectedCaseId((current) => current ?? nextCaseId);
      })
      .catch((error) => {
        if (!active) return;
        setCasesError(getErrorMessage(error));
      })
      .finally(() => {
        if (active) setCasesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [caseParam, isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated || activeTab !== 'files') return;
    let active = true;
    setSharedFilesLoading(true);
    getTenantSupportFiles()
      .then((data) => {
        if (!active) return;
        setSharedFiles(data);
      })
      .catch((error) => {
        if (!active) return;
        setSharedFilesError(getErrorMessage(error));
      })
      .finally(() => {
        if (active) setSharedFilesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [activeTab, isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated || !caseParam) return;
    if (cases.some((item) => item.id === caseParam)) {
      setSelectedCaseId(caseParam);
      return;
    }
    getHelpCase(caseParam)
      .then((payload) => {
        setCases((current) => [payload, ...current.filter((item) => item.id !== payload.id)]);
        setSelectedCaseId(payload.id);
      })
      .catch(() => {});
  }, [caseParam, cases, isAuthenticated]);

  async function handleArticleSearch() {
    if (!articleQuery.trim()) {
      setSearchResults([]);
      return;
    }
    try {
      const response = await searchHelpArticles({ q: articleQuery.trim(), current_path: from || undefined });
      setSearchResults(response.items);
      setSelectedArticleSlug(response.items[0]?.slug ?? null);
    } catch (error) {
      setArticlesError(getErrorMessage(error));
    }
  }

  async function handleAskAssistant(
    requestHuman: boolean = false,
    options?: { confirmLiveLookup?: boolean; accountOverride?: string | null },
  ) {
    setAssistantLoading(true);
    setAssistantError(null);
    setFeedbackStatus('idle');
    try {
      const nextAccountId = options?.accountOverride ?? accountId;
      const response = await queryHelpAssistant({
        question: assistantQuestion,
        thread_id: assistantThreadId,
        current_path: from,
        account_id: nextAccountId,
        action_id: actionId,
        finding_id: findingId,
        request_human: requestHuman,
        confirm_live_lookup: options?.confirmLiveLookup ?? false,
      });
      const nextThread = {
        thread_id: response.thread_id,
        current_path: from,
        turns: [
          ...(response.thread_id === assistantThread?.thread_id ? assistantThread.turns : []),
          {
            interaction_id: response.interaction_id,
            question: assistantQuestion,
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
          },
        ],
      } satisfies HelpAssistantThread;
      setAssistantThread(nextThread);
      setAssistantThreadId(response.thread_id);
      router.replace(buildHelpHref({ tab: 'assistant', from, accountId: nextAccountId ?? undefined, actionId, findingId, threadId: response.thread_id }), { scroll: false });
      if (response.escalated_case_id) {
        const casePayload = await getHelpCase(response.escalated_case_id);
        setCases((current) => [casePayload, ...current.filter((item) => item.id !== casePayload.id)]);
        setSelectedCaseId(casePayload.id);
        router.replace(buildHelpHref({ tab: 'cases', caseId: casePayload.id, from, accountId, actionId, findingId, threadId: response.thread_id }), { scroll: false });
      }
    } catch (error) {
      setAssistantError(getErrorMessage(error));
    } finally {
      setAssistantLoading(false);
    }
  }

  async function handleAssistantFeedback(helpful: boolean) {
    if (!assistantLatestTurn) return;
    try {
      const response = await sendHelpAssistantFeedback(assistantLatestTurn.interaction_id, { helpful });
      setAssistantThread((current) => {
        if (!current) return current;
        return {
          ...current,
          turns: current.turns.map((turn) =>
            turn.interaction_id === response.interaction_id ? { ...turn, helpful } : turn,
          ),
        };
      });
      setFeedbackStatus('saved');
    } catch {
      setFeedbackStatus('idle');
    }
  }

  async function handleApproveAssistantCase(interactionId: string) {
    setAssistantLoading(true);
    setAssistantError(null);
    try {
      const response = await approveHelpAssistantCase(interactionId);
      setAssistantThread((current) => {
        if (!current) return current;
        return {
          ...current,
          turns: current.turns.map((turn) =>
            turn.interaction_id === response.interaction_id
              ? { ...turn, escalated_case_id: response.escalated_case_id }
              : turn,
          ),
        };
      });
      if (response.escalated_case_id) {
        const casePayload = await getHelpCase(response.escalated_case_id);
        setCases((current) => [casePayload, ...current.filter((item) => item.id !== casePayload.id)]);
        setSelectedCaseId(casePayload.id);
        router.replace(buildHelpHref({ tab: 'cases', caseId: casePayload.id, from, accountId, actionId, findingId, threadId: assistantThreadId ?? response.thread_id }), { scroll: false });
      }
    } catch (error) {
      setAssistantError(getErrorMessage(error));
    } finally {
      setAssistantLoading(false);
    }
  }

  async function handleCreateCase() {
    setCreateLoading(true);
    setCasesError(null);
    try {
      const created = await createHelpCase({
        subject: createSubject.trim(),
        category: createCategory,
        priority: createPriority,
        body: createBody.trim(),
        source: from || accountId || actionId || findingId ? 'contextual_cta' : 'manual',
        current_path: from,
        account_id: accountId,
        action_id: actionId,
        finding_id: findingId,
      });
      let nextCase = created;
      const initialMessageId = created.messages[0]?.id;
      if (createAttachment && initialMessageId) {
        await uploadHelpCaseAttachmentDirect(created.id, initialMessageId, createAttachment);
        nextCase = await getHelpCase(created.id);
      }
      setCases((current) => [nextCase, ...current.filter((item) => item.id !== nextCase.id)]);
      setSelectedCaseId(nextCase.id);
      setCreateSubject('');
      setCreateCategory('other');
      setCreatePriority('normal');
      setCreateBody(contextualSummary ? `Please review this issue.\n\n${contextualSummary}` : '');
      setCreateAttachment(null);
      router.replace(buildHelpHref({ tab: 'cases', caseId: nextCase.id, from, accountId, actionId, findingId }), { scroll: false });
    } catch (error) {
      setCasesError(getErrorMessage(error));
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleReply() {
    if (!selectedCase) return;
    setReplyLoading(true);
    setCasesError(null);
    try {
      let updated = await replyToHelpCase(selectedCase.id, { body: replyBody.trim() });
      const newMessageId = updated.messages[updated.messages.length - 1]?.id;
      if (replyAttachment && newMessageId) {
        await uploadHelpCaseAttachmentDirect(selectedCase.id, newMessageId, replyAttachment);
        updated = await getHelpCase(selectedCase.id);
      }
      setCases((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setReplyBody('');
      setReplyAttachment(null);
    } catch (error) {
      setCasesError(getErrorMessage(error));
    } finally {
      setReplyLoading(false);
    }
  }

  async function handleDownloadSharedFile(fileId: string) {
    const response = await getSupportFileDownloadUrl(fileId);
    window.location.assign(response.download_url);
  }

  async function handleDownloadAttachment(caseId: string, attachmentId: string) {
    const response = await getHelpCaseAttachmentDownloadUrl(caseId, attachmentId);
    window.location.assign(response.download_url);
  }

  if (!authLoading && !isAuthenticated) {
    return (
      <AppShell title="Help">
        <div className="mx-auto w-full max-w-4xl">
          <div className={remediationInsetClass('default', 'p-8 text-center')}>
            <p className="mb-4 text-muted">Sign in to access the in-product Help Hub.</p>
            <div className="flex justify-center gap-3">
              <Button onClick={() => { window.location.href = '/login'; }}>Sign In</Button>
              <ButtonLink href="/help-center" variant="secondary">Open Public Help Center</ButtonLink>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Help">
      <div className="mx-auto w-full max-w-7xl space-y-6">
        <DashboardHero
          eyebrow="Support"
          title="Help Hub"
          description="Search curated help articles, ask the grounded assistant, open private support cases, and download files shared by support from one place."
          tone="accent"
        >
          <div className="space-y-4">
            {contextualSummary ? (
              <div className={remediationInsetClass('accent', 'px-4 py-3 text-xs text-text')}>
                Context captured for this session: {contextualSummary}
              </div>
            ) : null}
            <DashboardTabList>
              {HELP_TABS.map((tab) => (
                <DashboardTabButton
                  key={tab.value}
                  active={activeTab === tab.value}
                  onClick={() => router.replace(buildHelpHref({ tab: tab.value, from, accountId, actionId, findingId, caseId: selectedCaseId }), { scroll: false })}
                >
                  {tab.label}
                </DashboardTabButton>
              ))}
            </DashboardTabList>
          </div>
        </DashboardHero>

        {activeTab === 'help-center' ? (
          <section className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div className={remediationPanelClass('default', 'p-5')}>
              <div className="flex gap-2">
                <Input
                  value={articleQuery}
                  onChange={(event) => setArticleQuery(event.target.value)}
                  placeholder="Search onboarding, actions, integrations..."
                />
                <Button variant="secondary" onClick={() => handleArticleSearch()}>Search</Button>
              </div>
              {articlesError ? <p className="mt-4 text-sm text-danger">{articlesError}</p> : null}
              <div className="mt-5 space-y-3">
                {(articleQuery.trim() ? searchResults : articles).map((article) => (
                  <button
                    key={article.slug}
                    type="button"
                    onClick={() => setSelectedArticleSlug(article.slug)}
                    className={`w-full rounded-[1.5rem] border p-4 text-left transition ${
                      selectedArticle?.slug === article.slug ? 'border-accent/22 bg-accent/10 shadow-[0_18px_34px_-28px_rgba(10,113,255,0.8)]' : 'border-border/60 bg-[var(--card-inset)] hover:border-accent/30'
                    }`}
                  >
                    <p className="text-sm font-semibold text-text">{article.title}</p>
                    <p className="mt-1 text-sm text-muted">{articleExcerpt(article)}</p>
                  </button>
                ))}
                {!articlesLoading && (articleQuery.trim() ? searchResults : articles).length === 0 ? (
                  <p className="text-sm text-muted">No articles matched this search.</p>
                ) : null}
              </div>
            </div>
            <div className={remediationPanelClass('default', 'p-6')}>
              {selectedArticle ? (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    {selectedArticle.tags.map((tag) => (
                      <span key={tag} className="rounded-full border border-[var(--badge-border)] bg-[var(--badge-bg)] px-3 py-1 text-xs text-[var(--badge-text)]">{tag}</span>
                    ))}
                  </div>
                  <h2 className="mt-4 text-2xl font-semibold text-text">{selectedArticle.title}</h2>
                  <p className="mt-3 text-sm leading-7 whitespace-pre-line text-text/80">{selectedArticle.body}</p>
                </>
              ) : (
                <p className="text-sm text-muted">Select an article to read it here.</p>
              )}
            </div>
          </section>
        ) : null}

        {activeTab === 'assistant' ? (
          <section className="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
            <div className={remediationPanelClass('accent', 'p-6')}>
              <h2 className="text-xl font-semibold text-text">Ask the grounded assistant</h2>
              <p className="mt-2 text-sm leading-7 text-muted">
                The assistant answers briefly using published help articles plus platform-visible context from the route and entity you opened.
              </p>
              <textarea
                value={assistantQuestion}
                onChange={(event) => setAssistantQuestion(event.target.value)}
                className={dashboardFieldClass('mt-4 min-h-40')}
              />
              {assistantError ? <p className="mt-3 text-sm text-danger">{assistantError}</p> : null}
              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={() => handleAskAssistant(false)} isLoading={assistantLoading}>Ask assistant</Button>
                <Button variant="secondary" onClick={() => handleAskAssistant(true)} isLoading={assistantLoading}>
                  Escalate to support
                </Button>
              </div>
            </div>
            <div className={remediationPanelClass('default', 'p-6')}>
              <h2 className="text-xl font-semibold text-text">Assistant response</h2>
              {!assistantLatestTurn ? (
                <p className="mt-3 text-sm text-muted">Ask a question to receive a grounded answer with citations.</p>
              ) : (
                <div className="mt-4 space-y-5">
                  {assistantThread?.turns.map((turn) => (
                    <div key={turn.interaction_id} className={remediationInsetClass('default', 'p-4')}>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">You asked</p>
                      <p className="mt-2 text-sm leading-7 text-text">{turn.question}</p>
                      <div className={remediationInsetClass('accent', 'mt-4 p-4')}>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">Assistant</p>
                          <span className="rounded-full border border-[var(--badge-border)] bg-[var(--badge-bg)] px-3 py-1 text-xs font-medium text-[var(--badge-text)]">
                            Confidence: {turn.confidence}
                          </span>
                          {turn.escalated_case_id ? (
                            <ButtonLink href={buildHelpHref({ tab: 'cases', caseId: turn.escalated_case_id, threadId: assistantThreadId })} variant="secondary" size="sm">
                              Open escalated case
                            </ButtonLink>
                          ) : turn.suggested_case ? (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => handleApproveAssistantCase(turn.interaction_id)}
                              isLoading={assistantLoading}
                            >
                              Open support case
                            </Button>
                          ) : null}
                        </div>
                        <p className="mt-3 whitespace-pre-line text-sm leading-7 text-text/85">{turn.answer}</p>
                        {turn.live_lookup?.status === 'pending_confirmation' ? (
                          <div className={remediationInsetClass('warning', 'mt-4 p-3')}>
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-warning">Live IAM check available</p>
                            <p className="mt-2 text-sm text-text/80">{turn.live_lookup.message}</p>
                            <div className="mt-3">
                              <Button size="sm" onClick={() => handleAskAssistant(false, { confirmLiveLookup: true, accountOverride: turn.live_lookup?.account_id ?? accountId })}>
                                Run live IAM check
                              </Button>
                            </div>
                          </div>
                        ) : null}
                        {turn.live_lookup?.status === 'account_selection_required' && turn.live_lookup.candidate_accounts.length ? (
                          <div className={remediationInsetClass('warning', 'mt-4 p-3')}>
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-warning">Select an account</p>
                            <p className="mt-2 text-sm text-text/80">{turn.live_lookup.message}</p>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {turn.live_lookup.candidate_accounts.map((candidate) => (
                                <Button
                                  key={candidate.account_id}
                                  size="sm"
                                  variant="secondary"
                                  onClick={() => handleAskAssistant(false, { accountOverride: candidate.account_id })}
                                >
                                  {candidate.account_id}
                                </Button>
                              ))}
                            </div>
                          </div>
                        ) : null}
                        {turn.live_lookup?.status === 'executed' && turn.live_lookup.observations.length ? (
                          <div className={remediationInsetClass('accent', 'mt-4 p-4')}>
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">Live IAM observations</p>
                            <div className="mt-3 space-y-3">
                              {turn.live_lookup.observations.map((observation) => (
                                <div key={`${turn.interaction_id}-${observation.title}`} className={remediationInsetClass('default', 'p-3')}>
                                  <p className="text-sm font-semibold text-text">{observation.title}</p>
                                  <p className="mt-1 text-sm text-text/80">{observation.summary}</p>
                                  {observation.details.length ? (
                                    <p className="mt-2 text-sm text-muted">{observation.details.join(' | ')}</p>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                        {turn.live_lookup && ['disabled', 'failed'].includes(turn.live_lookup.status) && turn.live_lookup.message ? (
                          <div className={remediationInsetClass('warning', 'mt-4 p-3')}>
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-warning">Live lookup</p>
                            <p className="mt-2 text-sm text-text/80">{turn.live_lookup.message}</p>
                          </div>
                        ) : null}
                        {turn.context_gaps.length ? (
                          <div className={remediationInsetClass('warning', 'mt-4 p-3')}>
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-warning">Context gaps</p>
                            <p className="mt-2 text-sm text-text/80">{turn.context_gaps.join(' ')}</p>
                          </div>
                        ) : null}
                        <div className="mt-5 space-y-2">
                          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">Citations</p>
                          {turn.citations.map((citation) => (
                            <button
                              key={`${turn.interaction_id}-${citation.slug}`}
                              type="button"
                              onClick={() => {
                                setSelectedArticleSlug(citation.slug);
                                router.replace(buildHelpHref({ tab: 'help-center', from, accountId, actionId, findingId, threadId: assistantThreadId }), { scroll: false });
                              }}
                              className="block w-full rounded-[1.25rem] border border-border/60 bg-[var(--card-inset)] px-4 py-3 text-left transition hover:border-accent/30"
                            >
                              <p className="text-sm font-semibold text-text">{citation.title}</p>
                              <p className="mt-1 text-sm text-muted">{citation.summary}</p>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                  {assistantLatestTurn.follow_up_questions.length ? (
                    <div className={remediationInsetClass('default', 'p-4')}>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">Suggested follow-ups</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {assistantLatestTurn.follow_up_questions.map((question) => (
                          <Button key={question} variant="secondary" size="sm" onClick={() => setAssistantQuestion(question)}>
                            {question}
                          </Button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <div className="flex items-center gap-2">
                    <Button variant="secondary" size="sm" onClick={() => handleAssistantFeedback(true)}>Helpful</Button>
                    <Button variant="secondary" size="sm" onClick={() => handleAssistantFeedback(false)}>Not helpful</Button>
                    {feedbackStatus === 'saved' ? <span className="text-xs text-muted">Feedback saved.</span> : null}
                  </div>
                </div>
              )}
            </div>
          </section>
        ) : null}

        {activeTab === 'cases' ? (
          <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <div className="space-y-6">
              <div className={remediationPanelClass('default', 'p-6')}>
                <h2 className="text-xl font-semibold text-text">Open a support case</h2>
                <div className="mt-4 space-y-4">
                  <Input value={createSubject} onChange={(event) => setCreateSubject(event.target.value)} label="Subject" />
                  <label className="block text-sm font-medium text-text">
                    Category
                    <select
                      value={createCategory}
                      onChange={(event) => setCreateCategory(event.target.value)}
                      className={dashboardFieldClass('mt-1')}
                    >
                      {HELP_CASE_CATEGORIES.map((category) => (
                        <option key={category.value} value={category.value}>{category.label}</option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-sm font-medium text-text">
                    Priority
                    <select
                      value={createPriority}
                      onChange={(event) => setCreatePriority(event.target.value)}
                      className={dashboardFieldClass('mt-1')}
                    >
                      {['low', 'normal', 'high', 'urgent'].map((priority) => (
                        <option key={priority} value={priority}>{priority}</option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-sm font-medium text-text">
                    Details
                    <textarea
                      value={createBody}
                      onChange={(event) => setCreateBody(event.target.value)}
                      className={dashboardFieldClass('mt-1 min-h-32')}
                    />
                  </label>
                  <label className="block text-sm font-medium text-text">
                    Attach file
                    <input type="file" onChange={(event) => setCreateAttachment(event.target.files?.[0] ?? null)} className="mt-1 block w-full text-sm text-muted" />
                  </label>
                  <Button onClick={() => handleCreateCase()} isLoading={createLoading}>Create case</Button>
                </div>
              </div>
              <div className={remediationPanelClass('default', 'p-6')}>
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold text-text">My cases</h2>
                  <span className="text-sm text-muted">{cases.length}</span>
                </div>
                {casesError ? <p className="mt-3 text-sm text-danger">{casesError}</p> : null}
                <div className="mt-4 space-y-3">
                  {cases.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        setSelectedCaseId(item.id);
                        router.replace(buildHelpHref({ tab: 'cases', caseId: item.id, from, accountId, actionId, findingId }), { scroll: false });
                      }}
                      className={`w-full rounded-[1.5rem] border p-4 text-left transition ${
                        selectedCase?.id === item.id ? 'border-accent/22 bg-accent/10 shadow-[0_18px_34px_-28px_rgba(10,113,255,0.8)]' : 'border-border/60 bg-[var(--card-inset)] hover:border-accent/30'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-text">{item.subject}</p>
                        <span className="rounded-full border border-[var(--badge-border)] bg-[var(--badge-bg)] px-3 py-1 text-xs text-[var(--badge-text)]">{item.status}</span>
                      </div>
                      <p className="mt-2 text-xs text-muted">{item.category} | {item.priority} | {item.sla_state}</p>
                    </button>
                  ))}
                  {!casesLoading && cases.length === 0 ? <p className="text-sm text-muted">You have not opened any cases yet.</p> : null}
                </div>
              </div>
            </div>
            <div className={remediationPanelClass('default', 'p-6')}>
              {selectedCase ? (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-[var(--badge-border)] bg-[var(--badge-bg)] px-3 py-1 text-xs text-[var(--badge-text)]">{selectedCase.status}</span>
                    <span className="rounded-full border border-[var(--badge-border)] bg-[var(--badge-bg)] px-3 py-1 text-xs text-[var(--badge-text)]">{selectedCase.priority}</span>
                    <span className="rounded-full border border-[var(--badge-border)] bg-[var(--badge-bg)] px-3 py-1 text-xs text-[var(--badge-text)]">{selectedCase.sla_state}</span>
                  </div>
                  <h2 className="mt-4 text-2xl font-semibold text-text">{selectedCase.subject}</h2>
                  <div className="mt-5 space-y-4">
                    {selectedCase.messages.map((message) => (
                      <div key={message.id} className={remediationInsetClass('default', 'p-4')}>
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold text-text">{message.role}</p>
                          <p className="text-xs text-muted">{new Date(message.created_at).toLocaleString()}</p>
                        </div>
                        <p className="mt-3 whitespace-pre-line text-sm leading-7 text-text/85">{message.body}</p>
                        {message.attachments.length > 0 ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {message.attachments.map((attachment) => (
                              <button
                                key={attachment.id}
                                type="button"
                                onClick={() => handleDownloadAttachment(selectedCase.id, attachment.id)}
                                className="rounded-full border border-border/60 bg-[var(--card-inset)] px-3 py-1 text-xs text-muted hover:text-text"
                              >
                                {attachment.filename}
                              </button>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                  <div className={remediationInsetClass('accent', 'mt-6 space-y-3 p-4')}>
                    <textarea
                      value={replyBody}
                      onChange={(event) => setReplyBody(event.target.value)}
                      placeholder="Reply to support..."
                      className={dashboardFieldClass('min-h-28')}
                    />
                    <input type="file" onChange={(event) => setReplyAttachment(event.target.files?.[0] ?? null)} className="block w-full text-sm text-muted" />
                    <Button onClick={() => handleReply()} isLoading={replyLoading}>Send reply</Button>
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted">Select a case to view its full thread.</p>
              )}
            </div>
          </section>
        ) : null}

        {activeTab === 'files' ? (
          <section className={remediationPanelClass('default', 'p-6')}>
            <h2 className="text-xl font-semibold text-text">Shared files</h2>
            {sharedFilesError ? <p className="mt-3 text-sm text-danger">{sharedFilesError}</p> : null}
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left">
                  <tr>
                    <th className="px-4 py-3 font-semibold text-text">File</th>
                    <th className="px-4 py-3 font-semibold text-text">Message</th>
                    <th className="px-4 py-3 font-semibold text-text">Uploaded</th>
                    <th className="px-4 py-3 font-semibold text-text">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {sharedFiles.map((file) => (
                    <tr key={file.id} className="border-b border-border/40">
                      <td className="px-4 py-3 text-text">{file.filename}</td>
                      <td className="px-4 py-3 text-muted">{file.message ?? '—'}</td>
                      <td className="px-4 py-3 text-muted">{file.uploaded_at ? new Date(file.uploaded_at).toLocaleString() : '—'}</td>
                      <td className="px-4 py-3">
                        <Button variant="secondary" size="sm" onClick={() => handleDownloadSharedFile(file.id)}>Download</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!sharedFilesLoading && sharedFiles.length === 0 ? <p className="px-4 py-6 text-sm text-muted">No shared files are available yet.</p> : null}
            </div>
          </section>
        ) : null}

        <section className={remediationPanelClass('default', 'p-6')}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-text">Need public documentation instead?</h2>
              <p className="mt-2 text-sm text-muted">The same published article set is also available in the public help center.</p>
            </div>
            <div className="flex gap-2">
              <ButtonLink href="/help-center" variant="secondary">Open public help center</ButtonLink>
              <Link href="/faq" className="inline-flex items-center text-sm font-medium text-accent hover:underline">FAQ</Link>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

export default function HelpPage() {
  return (
    <Suspense fallback={<AppShell title="Help"><div className="p-10 text-center text-muted">Loading help...</div></AppShell>}>
      <HelpContent />
    </Suspense>
  );
}
