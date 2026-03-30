'use client';

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useAuth } from '@/contexts/AuthContext';
import { AuditLogFilters, AuditLogRecord, getAuditLog, getErrorMessage } from '@/lib/api';

const DEFAULT_LIMIT = 25;
const LIMIT_OPTIONS = [25, 50, 100, 200] as const;

interface AuditLogDraftFilters {
  actor_user_id: string;
  resource_type: string;
  resource_id: string;
  from_date: string;
  to_date: string;
}

function toFromDate(value: string): string | undefined {
  if (!value.trim()) return undefined;
  return `${value.trim()}T00:00:00Z`;
}

function toToDate(value: string): string | undefined {
  if (!value.trim()) return undefined;
  return `${value.trim()}T23:59:59Z`;
}

function formatDateTime(value: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function formatActor(value: string | null): string {
  if (!value) return 'system';
  if (value.length <= 8) return value;
  return `${value.slice(0, 8)}…`;
}

export default function AuditLogPage() {
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();
  const [items, setItems] = useState<AuditLogRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const [draftFilters, setDraftFilters] = useState<AuditLogDraftFilters>({
    actor_user_id: '',
    resource_type: '',
    resource_id: '',
    from_date: '',
    to_date: '',
  });
  const [appliedFilters, setAppliedFilters] = useState<AuditLogDraftFilters>({
    actor_user_id: '',
    resource_type: '',
    resource_id: '',
    from_date: '',
    to_date: '',
  });

  const canReadAuditLog = isAuthenticated && user?.role === 'admin';
  const isAccessDenied = !authLoading && isAuthenticated && user?.role !== 'admin';
  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + items.length, total);
  const canGoPrevious = offset > 0;
  const canGoNext = offset + limit < total;

  const query = useMemo<AuditLogFilters>(() => {
    const actorUserId = appliedFilters.actor_user_id.trim();
    const resourceType = appliedFilters.resource_type.trim();
    const resourceId = appliedFilters.resource_id.trim();
    return {
      actor_user_id: actorUserId || undefined,
      resource_type: resourceType || undefined,
      resource_id: resourceId || undefined,
      from_date: toFromDate(appliedFilters.from_date),
      to_date: toToDate(appliedFilters.to_date),
      limit,
      offset,
    };
  }, [appliedFilters, limit, offset]);

  const loadAuditLog = useCallback(async () => {
    if (!canReadAuditLog) return;

    setIsLoading(true);
    setError(null);
    try {
      const response = await getAuditLog(query);
      setItems(response.items);
      setTotal(response.total);
    } catch (err) {
      setItems([]);
      setTotal(0);
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [canReadAuditLog, query]);

  useEffect(() => {
    void loadAuditLog();
  }, [loadAuditLog]);

  function handleApplyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setAppliedFilters({ ...draftFilters });
  }

  function handleResetFilters() {
    const cleared: AuditLogDraftFilters = {
      actor_user_id: '',
      resource_type: '',
      resource_id: '',
      from_date: '',
      to_date: '',
    };
    setDraftFilters(cleared);
    setAppliedFilters(cleared);
    setOffset(0);
  }

  function handleLimitChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextLimit = Number(event.target.value);
    if (!Number.isFinite(nextLimit)) return;
    setLimit(nextLimit);
    setOffset(0);
  }

  if (!authLoading && !isAuthenticated) {
    return (
      <AppShell title="Audit Log">
        <div className="max-w-4xl mx-auto w-full">
          <div className="bg-surface border border-border rounded-xl p-8 text-center">
            <p className="text-muted mb-4">Please sign in to access tenant audit logs.</p>
            <Button onClick={() => (window.location.href = '/login')} variant="primary">
              Sign In
            </Button>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Audit Log">
      <div className="max-w-7xl mx-auto w-full space-y-6">
        <section className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-lg font-semibold text-text">Tenant Audit Events</h2>
          <p className="text-sm text-muted mt-1">
            Review actor, action, resource, and payload history for tenant activity.
          </p>
        </section>

        {isAccessDenied && (
          <section className="bg-warning/10 border border-warning/30 rounded-xl p-4" role="alert">
            <p className="text-sm font-medium text-warning">Access denied</p>
            <p className="text-sm text-warning/90 mt-1">Only tenant admins can view audit logs.</p>
          </section>
        )}

        {canReadAuditLog && (
          <>
            <section className="bg-surface border border-border rounded-xl p-5">
              <form className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4" onSubmit={handleApplyFilters}>
                <Input
                  label="Actor User ID"
                  value={draftFilters.actor_user_id}
                  onChange={(event) =>
                    setDraftFilters((previous) => ({ ...previous, actor_user_id: event.target.value }))
                  }
                  placeholder="UUID"
                />
                <Input
                  label="Resource Type"
                  value={draftFilters.resource_type}
                  onChange={(event) =>
                    setDraftFilters((previous) => ({ ...previous, resource_type: event.target.value }))
                  }
                  placeholder="aws_account"
                />
                <Input
                  label="Resource ID"
                  value={draftFilters.resource_id}
                  onChange={(event) =>
                    setDraftFilters((previous) => ({ ...previous, resource_id: event.target.value }))
                  }
                  placeholder="Resource identifier"
                />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    label="From Date"
                    type="date"
                    value={draftFilters.from_date}
                    onChange={(event) =>
                      setDraftFilters((previous) => ({ ...previous, from_date: event.target.value }))
                    }
                  />
                  <Input
                    label="To Date"
                    type="date"
                    value={draftFilters.to_date}
                    onChange={(event) =>
                      setDraftFilters((previous) => ({ ...previous, to_date: event.target.value }))
                    }
                  />
                </div>

                <div className="md:col-span-2 xl:col-span-4 flex flex-wrap items-center gap-3">
                  <Button type="submit" variant="primary" disabled={isLoading}>
                    Apply filters
                  </Button>
                  <Button type="button" variant="secondary" onClick={handleResetFilters} disabled={isLoading}>
                    Reset
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => void loadAuditLog()} disabled={isLoading}>
                    Refresh
                  </Button>
                </div>
              </form>
            </section>

            <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-muted">
                  {total} events
                  {total > 0 && (
                    <>
                      {' '}• Showing {pageStart}-{pageEnd}
                    </>
                  )}
                </p>

                <div className="flex items-center gap-3">
                  <label className="text-sm text-muted" htmlFor="audit-log-limit">
                    Results Per Page
                  </label>
                  <select
                    id="audit-log-limit"
                    value={String(limit)}
                    onChange={handleLimitChange}
                    className="h-10 rounded-xl border border-border bg-dropdown-bg px-3 text-sm text-text"
                  >
                    {LIMIT_OPTIONS.map((option) => (
                      <option key={option} value={String(option)}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {error && (
                <div className="p-4 rounded-xl border border-danger/40 bg-danger/10 text-danger" role="alert">
                  <p className="text-sm font-medium">Error loading audit events</p>
                  <p className="text-sm mt-1">{error}</p>
                </div>
              )}

              {isLoading && (
                <div className="rounded-xl border border-border p-6 text-center">
                  <p className="text-muted animate-pulse">Loading audit events…</p>
                </div>
              )}

              {!isLoading && !error && items.length === 0 && (
                <div className="rounded-xl border border-border p-8 text-center">
                  <p className="text-text font-medium">No audit events found</p>
                  <p className="text-muted text-sm mt-1">Try widening your filters or date range.</p>
                </div>
              )}

              {!isLoading && !error && items.length > 0 && (
                <div className="overflow-x-auto rounded-xl border border-border">
                  <table className="w-full text-sm">
                    <thead className="bg-bg/60 border-b border-border">
                      <tr className="text-left text-muted">
                        <th className="px-4 py-3">When</th>
                        <th className="px-4 py-3">Actor</th>
                        <th className="px-4 py-3">Action</th>
                        <th className="px-4 py-3">Resource</th>
                        <th className="px-4 py-3">Payload</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => (
                        <tr key={item.id} className="border-b border-border/60 align-top">
                          <td className="px-4 py-3 whitespace-nowrap">{formatDateTime(item.timestamp ?? item.created_at)}</td>
                          <td className="px-4 py-3 font-mono text-xs">{formatActor(item.actor_user_id)}</td>
                          <td className="px-4 py-3">{item.action}</td>
                          <td className="px-4 py-3">
                            <p className="text-text">{item.resource_type}</p>
                            <p className="font-mono text-xs text-muted break-all">{item.resource_id}</p>
                          </td>
                          <td className="px-4 py-3">
                            {item.payload ? (
                              <details>
                                <summary className="cursor-pointer text-accent hover:text-accent-hover">
                                  View payload
                                </summary>
                                <pre className="mt-2 whitespace-pre-wrap text-xs text-muted">{JSON.stringify(item.payload, null, 2)}</pre>
                              </details>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="flex items-center justify-end gap-3">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!canGoPrevious || isLoading}
                  onClick={() => setOffset((previous) => Math.max(0, previous - limit))}
                >
                  Previous
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!canGoNext || isLoading}
                  onClick={() => setOffset((previous) => previous + limit)}
                >
                  Next page
                </Button>
              </div>
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}
