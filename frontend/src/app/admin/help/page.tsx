'use client';

import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useAuth } from '@/contexts/AuthContext';
import {
  getAdminHelpCase,
  getAdminHelpCaseAttachmentDownloadUrl,
  getErrorMessage,
  HelpCase,
  listAdminHelpCases,
  replyToAdminHelpCase,
  updateAdminHelpCase,
  uploadAdminHelpCaseAttachmentDirect,
} from '@/lib/api';

export default function AdminHelpPage() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [tenantFilter, setTenantFilter] = useState('');
  const [slaFilter, setSlaFilter] = useState('');
  const [cases, setCases] = useState<HelpCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState('');
  const [replyInternal, setReplyInternal] = useState(false);
  const [replyAttachment, setReplyAttachment] = useState<File | null>(null);
  const [replyLoading, setReplyLoading] = useState(false);
  const [statusUpdate, setStatusUpdate] = useState('');
  const [priorityUpdate, setPriorityUpdate] = useState('');
  const [assignmentUpdate, setAssignmentUpdate] = useState('');
  const [updateLoading, setUpdateLoading] = useState(false);

  const selectedCase = useMemo(
    () => cases.find((item) => item.id === selectedCaseId) ?? null,
    [cases, selectedCaseId],
  );

  useEffect(() => {
    if (!isAuthenticated || !user?.is_saas_admin) {
      setIsLoading(false);
      return;
    }
    let active = true;
    setIsLoading(true);
    listAdminHelpCases({
      status: statusFilter || undefined,
      priority: priorityFilter || undefined,
      tenant_id: tenantFilter || undefined,
      sla_state: slaFilter || undefined,
    })
      .then((response) => {
        if (!active) return;
        setCases(response.items);
        setSelectedCaseId((current) => current ?? response.items[0]?.id ?? null);
      })
      .catch((value) => {
        if (!active) return;
        setError(getErrorMessage(value));
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [isAuthenticated, priorityFilter, slaFilter, statusFilter, tenantFilter, user?.is_saas_admin]);

  useEffect(() => {
    if (!selectedCase) return;
    setStatusUpdate(selectedCase.status);
    setPriorityUpdate(selectedCase.priority);
    setAssignmentUpdate(selectedCase.assigned_saas_admin_user_id ?? '');
  }, [selectedCase]);

  async function handleReply() {
    if (!selectedCase) return;
    setReplyLoading(true);
    setError(null);
    try {
      let updated = await replyToAdminHelpCase(selectedCase.id, { body: replyBody.trim() }, replyInternal);
      const messageId = updated.messages[updated.messages.length - 1]?.id;
      if (replyAttachment && messageId) {
        await uploadAdminHelpCaseAttachmentDirect(selectedCase.id, messageId, replyAttachment, replyInternal);
        updated = await getAdminHelpCase(selectedCase.id);
      }
      setCases((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setReplyBody('');
      setReplyInternal(false);
      setReplyAttachment(null);
    } catch (value) {
      setError(getErrorMessage(value));
    } finally {
      setReplyLoading(false);
    }
  }

  async function handleUpdateCase() {
    if (!selectedCase) return;
    setUpdateLoading(true);
    setError(null);
    try {
      const updated = await updateAdminHelpCase(selectedCase.id, {
        status: statusUpdate,
        priority: priorityUpdate,
        assigned_saas_admin_user_id: assignmentUpdate.trim() || null,
      });
      setCases((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (value) {
      setError(getErrorMessage(value));
    } finally {
      setUpdateLoading(false);
    }
  }

  async function handleDownloadAttachment(caseId: string, attachmentId: string) {
    const response = await getAdminHelpCaseAttachmentDownloadUrl(caseId, attachmentId);
    window.location.assign(response.download_url);
  }

  if (!authLoading && (!isAuthenticated || !user?.is_saas_admin)) {
    return (
      <AppShell title="Admin Help">
        <div className="rounded-xl border border-border bg-surface p-8 text-center">
          <p className="text-muted">SaaS admin access is required.</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Admin Help" wide>
      <div className="mx-auto w-full max-w-7xl space-y-6">
        <section className="rounded-3xl border border-border bg-surface p-6">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <label className="block text-sm font-medium text-text">
              Status
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="mt-1 w-full rounded-2xl border border-border bg-bg px-3 py-2 text-sm text-text">
                <option value="">All</option>
                {['new', 'triaging', 'waiting_on_customer', 'resolved', 'closed'].map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium text-text">
              Priority
              <select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)} className="mt-1 w-full rounded-2xl border border-border bg-bg px-3 py-2 text-sm text-text">
                <option value="">All</option>
                {['low', 'normal', 'high', 'urgent'].map((priority) => (
                  <option key={priority} value={priority}>{priority}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium text-text">
              SLA
              <select value={slaFilter} onChange={(event) => setSlaFilter(event.target.value)} className="mt-1 w-full rounded-2xl border border-border bg-bg px-3 py-2 text-sm text-text">
                <option value="">All</option>
                {['awaiting_support', 'awaiting_customer', 'overdue', 'resolved'].map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
            <Input label="Tenant ID" value={tenantFilter} onChange={(event) => setTenantFilter(event.target.value)} placeholder="Filter by tenant UUID" />
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-3xl border border-border bg-surface p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-text">Support inbox</h2>
              <span className="text-sm text-muted">{cases.length}</span>
            </div>
            {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
            <div className="mt-4 space-y-3">
              {cases.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedCaseId(item.id)}
                  className={`w-full rounded-2xl border p-4 text-left transition ${
                    selectedCase?.id === item.id ? 'border-accent bg-accent/5' : 'border-border bg-bg/50 hover:border-accent/30'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-text">{item.subject}</p>
                    <span className="rounded-full bg-bg px-3 py-1 text-xs text-muted">{item.sla_state}</span>
                  </div>
                  <p className="mt-2 text-xs text-muted">{item.requester_email} | {item.status} | {item.priority}</p>
                </button>
              ))}
              {!isLoading && cases.length === 0 ? <p className="text-sm text-muted">No help cases matched the current filters.</p> : null}
            </div>
          </div>
          <div className="rounded-3xl border border-border bg-surface p-6">
            {selectedCase ? (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-bg px-3 py-1 text-xs text-muted">{selectedCase.status}</span>
                  <span className="rounded-full bg-bg px-3 py-1 text-xs text-muted">{selectedCase.priority}</span>
                  <span className="rounded-full bg-bg px-3 py-1 text-xs text-muted">{selectedCase.requester_email}</span>
                </div>
                <h2 className="mt-4 text-2xl font-semibold text-text">{selectedCase.subject}</h2>
                <p className="mt-2 text-sm text-muted">Tenant: {selectedCase.tenant_id}</p>
                <div className="mt-5 grid gap-4 md:grid-cols-3">
                  <label className="block text-sm font-medium text-text">
                    Status
                    <select value={statusUpdate} onChange={(event) => setStatusUpdate(event.target.value)} className="mt-1 w-full rounded-2xl border border-border bg-bg px-3 py-2 text-sm text-text">
                      {['new', 'triaging', 'waiting_on_customer', 'resolved', 'closed'].map((status) => (
                        <option key={status} value={status}>{status}</option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-sm font-medium text-text">
                    Priority
                    <select value={priorityUpdate} onChange={(event) => setPriorityUpdate(event.target.value)} className="mt-1 w-full rounded-2xl border border-border bg-bg px-3 py-2 text-sm text-text">
                      {['low', 'normal', 'high', 'urgent'].map((priority) => (
                        <option key={priority} value={priority}>{priority}</option>
                      ))}
                    </select>
                  </label>
                  <Input label="Assign SaaS admin" value={assignmentUpdate} onChange={(event) => setAssignmentUpdate(event.target.value)} placeholder="User UUID" />
                </div>
                <div className="mt-4">
                  <Button variant="secondary" onClick={() => handleUpdateCase()} isLoading={updateLoading}>Save case updates</Button>
                </div>
                <div className="mt-6 space-y-4">
                  {selectedCase.messages.map((message) => (
                    <div key={message.id} className={`rounded-2xl border p-4 ${message.internal_only ? 'border-warning/30 bg-warning/10' : 'border-border bg-bg/50'}`}>
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-text">{message.role}{message.internal_only ? ' (internal)' : ''}</p>
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
                              className="rounded-full border border-border px-3 py-1 text-xs text-muted hover:text-text"
                            >
                              {attachment.filename}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
                <div className="mt-6 space-y-3 rounded-2xl border border-border bg-bg/40 p-4">
                  <textarea
                    value={replyBody}
                    onChange={(event) => setReplyBody(event.target.value)}
                    placeholder="Reply to the requester or leave an internal note..."
                    className="min-h-32 w-full rounded-2xl border border-border bg-bg px-4 py-3 text-sm text-text"
                  />
                  <label className="flex items-center gap-2 text-sm text-text">
                    <input type="checkbox" checked={replyInternal} onChange={(event) => setReplyInternal(event.target.checked)} />
                    Internal note only
                  </label>
                  <input type="file" onChange={(event) => setReplyAttachment(event.target.files?.[0] ?? null)} className="block w-full text-sm text-muted" />
                  <Button onClick={() => handleReply()} isLoading={replyLoading}>Send reply</Button>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted">Select a case to review the full thread and respond.</p>
            )}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
