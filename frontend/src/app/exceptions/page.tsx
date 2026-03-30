'use client';

import { Suspense, useEffect, useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { SelectDropdown } from '@/components/ui/SelectDropdown';
import { Input } from '@/components/ui/Input';
import { TenantIdForm } from '@/components/TenantIdForm';
import {
  applyFindingGroupAction,
  getExceptions,
  revokeException,
  ExceptionListItem,
  ExceptionsFilters,
  getErrorMessage,
} from '@/lib/api';
import { useTenantId } from '@/lib/tenant';
import { useAuth } from '@/contexts/AuthContext';

const LIMIT = 50;

function defaultGroupSuppressExpiryDate() {
  const next = new Date();
  next.setDate(next.getDate() + 30);
  return next.toISOString().split('T')[0];
}

function ExceptionsPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { tenantId, setTenantId } = useTenantId();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [exceptions, setExceptions] = useState<ExceptionListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [activeOnly, setActiveOnly] = useState(true);
  const [entityTypeFilter, setEntityTypeFilter] = useState<'finding' | 'action' | ''>('');
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revokeModalOpen, setRevokeModalOpen] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<ExceptionListItem | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);
  const [groupSuppressOpen, setGroupSuppressOpen] = useState(false);
  const [groupSuppressReason, setGroupSuppressReason] = useState('');
  const [groupSuppressExpiry, setGroupSuppressExpiry] = useState('');
  const [groupSuppressTicketLink, setGroupSuppressTicketLink] = useState('');
  const [groupSuppressError, setGroupSuppressError] = useState<string | null>(null);
  const [groupSuppressNotice, setGroupSuppressNotice] = useState<string | null>(null);
  const [isSubmittingGroupSuppress, setIsSubmittingGroupSuppress] = useState(false);

  const effectiveTenantId = isAuthenticated ? undefined : tenantId;
  const showContent = isAuthenticated || tenantId;

  const groupedSuppressScope = useMemo(() => {
    const action = searchParams.get('group_action');
    const groupKey = searchParams.get('group_key');
    if (action !== 'suppress' || !groupKey) return null;
    return {
      action,
      group_key: groupKey,
      control_id: searchParams.get('control_id') || undefined,
      resource_type: searchParams.get('resource_type') || undefined,
      account_id: searchParams.get('account_id') || undefined,
      region: searchParams.get('region') || undefined,
      severity: searchParams.get('severity') || undefined,
      source: searchParams.get('source') || undefined,
      status: searchParams.get('status') || undefined,
      resource_id: searchParams.get('resource_id') || undefined,
    };
  }, [searchParams]);

  const fetchExceptions = useCallback(async () => {
    if (effectiveTenantId === undefined && !isAuthenticated) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const filters: ExceptionsFilters = {
        limit: LIMIT,
        offset,
        active_only: activeOnly,
      };
      if (entityTypeFilter) filters.entity_type = entityTypeFilter;

      const response = await getExceptions(filters, effectiveTenantId);
      setExceptions(response.items);
      setTotal(response.total);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [effectiveTenantId, isAuthenticated, activeOnly, entityTypeFilter, offset]);

  useEffect(() => {
    fetchExceptions();
  }, [fetchExceptions]);

  useEffect(() => {
    if (!groupedSuppressScope) return;
    setGroupSuppressOpen(true);
    setGroupSuppressError(null);
    setGroupSuppressNotice(null);
    setGroupSuppressExpiry((current) => current || defaultGroupSuppressExpiryDate());
  }, [groupedSuppressScope]);

  const clearGroupedSuppressQuery = useCallback(() => {
    const next = new URLSearchParams(searchParams.toString());
    [
      'group_action',
      'group_key',
      'account_id',
      'region',
      'severity',
      'source',
      'status',
      'control_id',
      'resource_type',
      'resource_id',
    ].forEach((key) => next.delete(key));
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  }, [pathname, router, searchParams]);

  const handleRevoke = async () => {
    if (!revokeTarget) return;

    setIsRevoking(true);
    try {
      await revokeException(revokeTarget.id, effectiveTenantId);
      setRevokeModalOpen(false);
      setRevokeTarget(null);
      fetchExceptions();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsRevoking(false);
    }
  };

  const openRevokeModal = (exception: ExceptionListItem) => {
    setRevokeTarget(exception);
    setRevokeModalOpen(true);
  };

  const handleCloseGroupSuppress = useCallback(() => {
    if (isSubmittingGroupSuppress) return;
    setGroupSuppressOpen(false);
    setGroupSuppressReason('');
    setGroupSuppressTicketLink('');
    setGroupSuppressError(null);
    setGroupSuppressExpiry(defaultGroupSuppressExpiryDate());
    clearGroupedSuppressQuery();
  }, [clearGroupedSuppressQuery, isSubmittingGroupSuppress]);

  const handleSubmitGroupSuppress = useCallback(async () => {
    if (!groupedSuppressScope) return;
    const reason = groupSuppressReason.trim();
    if (reason.length < 10) {
      setGroupSuppressError('Reason must be at least 10 characters.');
      return;
    }
    if (!groupSuppressExpiry) {
      setGroupSuppressError('Expiry date is required.');
      return;
    }

    const expiryDate = new Date(groupSuppressExpiry);
    if (expiryDate <= new Date()) {
      setGroupSuppressError('Expiry date must be in the future.');
      return;
    }

    setIsSubmittingGroupSuppress(true);
    setGroupSuppressError(null);
    try {
      const result = await applyFindingGroupAction({
        action: 'suppress',
        group_key: groupedSuppressScope.group_key,
        reason,
        ticket_link: groupSuppressTicketLink.trim() || undefined,
        expires_at: expiryDate.toISOString(),
        account_id: groupedSuppressScope.account_id,
        region: groupedSuppressScope.region,
        severity: groupedSuppressScope.severity,
        source: groupedSuppressScope.source,
        status: groupedSuppressScope.status,
        control_id: groupedSuppressScope.control_id,
        resource_id: groupedSuppressScope.resource_id,
      });
      setGroupSuppressNotice(
        `Suppress Group applied to ${result.matched_findings} findings (${result.exceptions_created} created, ${result.exceptions_updated} updated).`
      );
      setGroupSuppressOpen(false);
      setGroupSuppressReason('');
      setGroupSuppressTicketLink('');
      setGroupSuppressExpiry(defaultGroupSuppressExpiryDate());
      clearGroupedSuppressQuery();
      await fetchExceptions();
    } catch (err) {
      setGroupSuppressError(getErrorMessage(err));
    } finally {
      setIsSubmittingGroupSuppress(false);
    }
  }, [
    clearGroupedSuppressQuery,
    fetchExceptions,
    groupSuppressExpiry,
    groupSuppressReason,
    groupSuppressTicketLink,
    groupedSuppressScope,
  ]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <AppShell title="Exceptions">
      <div className="max-w-6xl mx-auto w-full">
        {!showContent && !authLoading && isAuthenticated && <TenantIdForm onSave={setTenantId} />}

        {showContent && (
          <>
            {/* Header */}
            <div className="mb-6">
              <h1 className="text-2xl font-semibold text-text mb-2">Exceptions</h1>
              <p className="text-muted text-sm">
                Manage suppressed findings and actions. Exceptions expire automatically.
              </p>
            </div>

            {groupSuppressNotice && (
              <div className="mb-6 rounded-xl border border-accent/20 bg-accent/10 p-4">
                <p className="text-sm font-medium text-text">{groupSuppressNotice}</p>
              </div>
            )}

            {groupedSuppressScope && (
              <div className="mb-6 rounded-xl border border-warning/20 bg-warning/10 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-text">Grouped suppression scope ready</p>
                    <p className="mt-1 text-sm text-muted">
                      {groupedSuppressScope.control_id || 'Unknown control'} · {groupedSuppressScope.resource_type || 'Unknown resource'} · {groupedSuppressScope.account_id || 'Unknown account'} · {groupedSuppressScope.region || 'Unknown region'}
                    </p>
                  </div>
                  <Button size="sm" variant="secondary" onClick={() => setGroupSuppressOpen(true)}>
                    Open suppress screen
                  </Button>
                </div>
              </div>
            )}

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-4 mb-6">
              {/* Active/Expired tabs */}
              <div className="flex items-center gap-1 p-1 bg-surface rounded-xl border border-border">
                <button
                  type="button"
                  onClick={() => {
                    setActiveOnly(true);
                    setOffset(0);
                  }}
                  className={`
                    px-4 py-2 text-sm font-medium rounded-xl transition-all duration-150
                    ${activeOnly
                      ? 'bg-accent text-bg shadow-sm'
                      : 'text-muted hover:text-text hover:bg-bg'
                    }
                  `}
                >
                  Active
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setActiveOnly(false);
                    setOffset(0);
                  }}
                  className={`
                    px-4 py-2 text-sm font-medium rounded-xl transition-all duration-150
                    ${!activeOnly
                      ? 'bg-accent text-bg shadow-sm'
                      : 'text-muted hover:text-text hover:bg-bg'
                    }
                  `}
                >
                  All
                </button>
              </div>

              {/* Entity type filter */}
              <SelectDropdown<'finding' | 'action' | ''>
                value={entityTypeFilter}
                onValueChange={(value) => {
                  setEntityTypeFilter(value);
                  setOffset(0);
                }}
                options={[
                  { value: '', label: 'All Types' },
                  { value: 'finding', label: 'Findings' },
                  { value: 'action', label: 'Actions' },
                ]}
                aria-label="Filter by entity type"
              />

              <div className="flex-1" />

              <Button
                variant="secondary"
                size="sm"
                onClick={fetchExceptions}
                disabled={isLoading}
                className="h-10 px-4 shrink-0 whitespace-nowrap"
                leftIcon={
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                  </svg>
                }
              >
                Refresh
              </Button>
            </div>

            {/* Error */}
            {error && (
              <div className="mb-6 p-4 bg-danger/10 border border-danger/20 rounded-xl">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-danger mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                  </svg>
                  <div>
                    <p className="text-sm font-medium text-danger">Error loading exceptions</p>
                    <p className="text-sm text-danger/80">{error}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Loading */}
            {isLoading && (
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="bg-surface border border-border rounded-xl p-6 animate-pulse">
                    <div className="h-5 bg-border rounded w-2/3 mb-3" />
                    <div className="h-4 bg-border rounded w-full mb-2" />
                    <div className="h-4 bg-border rounded w-3/4" />
                  </div>
                ))}
              </div>
            )}

            {/* Empty state */}
            {!isLoading && exceptions.length === 0 && (
              <div className="text-center py-12">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-surface border border-border mb-4">
                  <svg className="w-8 h-8 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-text mb-2">
                  {activeOnly ? 'No active exceptions' : 'No exceptions'}
                </h3>
                <p className="text-muted text-sm">
                  {activeOnly
                    ? 'Create exceptions from finding or action detail pages to suppress items.'
                    : 'No exceptions have been created yet.'}
                </p>
              </div>
            )}

            {/* Exceptions list */}
            {!isLoading && exceptions.length > 0 && (
              <div className="space-y-5">
                {exceptions.map((exception) => (
                  <div
                    key={exception.id}
                    className="bg-surface border border-accent/30 rounded-xl p-6 shadow-glow hover:border-accent/50 transition-all duration-200"
                  >
                    <div className="flex items-start justify-between gap-4 mb-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant={exception.entity_type === 'finding' ? 'info' : 'warning'}>
                            {exception.entity_type}
                          </Badge>
                          {exception.is_expired && (
                            <Badge variant="danger">Expired</Badge>
                          )}
                        </div>
                        <p className="text-text text-sm leading-relaxed mb-3">
                          {exception.reason}
                        </p>
                        {exception.ticket_link && (
                          <a
                            href={exception.ticket_link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-accent hover:text-accent-hover inline-flex items-center gap-1"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
                            </svg>
                            View ticket
                          </a>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Link
                          href={`/${exception.entity_type === 'finding' ? 'findings' : 'actions'}/${exception.entity_id}`}
                          className="text-sm text-accent hover:text-accent-hover transition-colors"
                        >
                          View {exception.entity_type}
                        </Link>
                        {isAuthenticated && !exception.is_expired && (
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => openRevokeModal(exception)}
                          >
                            Revoke
                          </Button>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-5 pt-4 border-t border-border text-xs text-muted">
                      <div className="flex items-center gap-1.5">
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                        </svg>
                        <span>{exception.approved_by_email || 'Unknown'}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
                        </svg>
                        <span>
                          {exception.is_expired ? 'Expired' : `Expires ${formatDate(exception.expires_at)}`}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span>Created {formatDate(exception.created_at)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination */}
            {!isLoading && total > LIMIT && (
              <div className="mt-8 flex items-center justify-between">
                <p className="text-sm text-muted">
                  Showing {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setOffset(Math.max(0, offset - LIMIT))}
                    disabled={offset === 0}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setOffset(offset + LIMIT)}
                    disabled={offset + LIMIT >= total}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {groupedSuppressScope && (
        <Modal
          isOpen={groupSuppressOpen}
          onClose={handleCloseGroupSuppress}
          title="Suppress Group"
          size="lg"
          variant="dashboard"
        >
          <div className="space-y-6">
            <div className="rounded-xl border border-warning/20 bg-warning/10 p-4">
              <p className="text-sm font-medium text-text">This suppression will target the current grouped findings scope.</p>
              <p className="mt-2 text-sm text-muted">
                {groupedSuppressScope.control_id || 'Unknown control'} · {groupedSuppressScope.resource_type || 'Unknown resource'} · {groupedSuppressScope.account_id || 'Unknown account'} · {groupedSuppressScope.region || 'Unknown region'}
              </p>
              {(groupedSuppressScope.severity || groupedSuppressScope.source || groupedSuppressScope.status || groupedSuppressScope.resource_id) && (
                <p className="mt-2 text-xs text-muted">
                  Active filters:
                  {groupedSuppressScope.severity ? ` severity=${groupedSuppressScope.severity}` : ''}
                  {groupedSuppressScope.source ? ` source=${groupedSuppressScope.source}` : ''}
                  {groupedSuppressScope.status ? ` status=${groupedSuppressScope.status}` : ''}
                  {groupedSuppressScope.resource_id ? ` resource_id=${groupedSuppressScope.resource_id}` : ''}
                </p>
              )}
            </div>

            <div className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-text" htmlFor="group-suppress-reason">
                  Reason
                </label>
                <textarea
                  id="group-suppress-reason"
                  value={groupSuppressReason}
                  onChange={(event) => setGroupSuppressReason(event.target.value)}
                  rows={4}
                  className="w-full rounded-xl border border-border bg-bg/80 px-4 py-3 text-sm text-text outline-none transition focus:border-accent"
                  placeholder="Explain why this grouped set of findings should be suppressed."
                  disabled={isSubmittingGroupSuppress}
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium text-text" htmlFor="group-suppress-expiry">
                    Expires On
                  </label>
                  <Input
                    id="group-suppress-expiry"
                    type="date"
                    value={groupSuppressExpiry}
                    onChange={(event) => setGroupSuppressExpiry(event.target.value)}
                    min={new Date().toISOString().split('T')[0]}
                    disabled={isSubmittingGroupSuppress}
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-text" htmlFor="group-suppress-ticket-link">
                    Ticket Link
                  </label>
                  <Input
                    id="group-suppress-ticket-link"
                    type="url"
                    value={groupSuppressTicketLink}
                    onChange={(event) => setGroupSuppressTicketLink(event.target.value)}
                    placeholder="https://jira.example.com/TICKET-123"
                    disabled={isSubmittingGroupSuppress}
                  />
                </div>
              </div>
            </div>

            {groupSuppressError && (
              <div className="rounded-xl border border-danger/20 bg-danger/10 p-4">
                <p className="text-sm font-medium text-danger">{groupSuppressError}</p>
              </div>
            )}

            <div className="flex gap-3">
              <Button
                variant="secondary"
                onClick={handleCloseGroupSuppress}
                disabled={isSubmittingGroupSuppress}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleSubmitGroupSuppress}
                isLoading={isSubmittingGroupSuppress}
                className="flex-1"
              >
                {isSubmittingGroupSuppress ? 'Applying...' : 'Apply Suppression'}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Revoke confirmation modal */}
      {revokeTarget && (
        <Modal
          isOpen={revokeModalOpen}
          onClose={() => !isRevoking && setRevokeModalOpen(false)}
          title="Revoke Exception"
          size="sm"
        >
          <div className="space-y-4">
            <p className="text-sm text-muted">
              Are you sure you want to revoke this exception? The {revokeTarget.entity_type} will 
              return to the active list.
            </p>
            <div className="p-3 bg-bg border border-border rounded-xl">
              <p className="text-xs text-muted mb-1">Reason:</p>
              <p className="text-sm text-text">{revokeTarget.reason}</p>
            </div>
            <div className="flex gap-3">
              <Button
                variant="secondary"
                onClick={() => setRevokeModalOpen(false)}
                disabled={isRevoking}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={handleRevoke}
                isLoading={isRevoking}
                className="flex-1"
              >
                {isRevoking ? 'Revoking...' : 'Revoke Exception'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </AppShell>
  );
}

export default function ExceptionsPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="Exceptions">
          <div className="p-10 text-center text-muted">Loading exceptions...</div>
        </AppShell>
      }
    >
      <ExceptionsPageContent />
    </Suspense>
  );
}
