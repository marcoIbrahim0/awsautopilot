'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { PlaceholdersAndVanishInput } from '@/components/ui/placeholders-and-vanish-input';
import { SelectDropdown } from '@/components/ui/SelectDropdown';
import { TenantIdForm } from '@/components/TenantIdForm';
import { useAuth } from '@/contexts/AuthContext';
import {
  DashboardFilterBar,
  DashboardHero,
  DashboardTableCard,
  remediationInsetClass,
} from '@/components/ui/remediation-surface';
import { useTenantId } from '@/lib/tenant';
import { ActionListItem, getAccounts, getActions, getErrorMessage } from '@/lib/api';

const PAGE_LIMIT = 200;

function titleCaseToken(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatMatrixLabel(action: ActionListItem): string {
  const risk = titleCaseToken(action.business_impact.technical_risk_tier);
  const criticality = titleCaseToken(action.business_impact.criticality.tier);
  return `${risk} x ${criticality}`;
}

export default function CreatePrBundlePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { tenantId, setTenantId } = useTenantId();
  const effectiveTenantId = isAuthenticated ? undefined : tenantId;
  const showContent = isAuthenticated || Boolean(tenantId);

  const [actions, setActions] = useState<ActionListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');
  const [accountFilter, setAccountFilter] = useState('');
  const [regionFilter, setRegionFilter] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [availableAccounts, setAvailableAccounts] = useState<string[]>([]);
  const [availableRegions, setAvailableRegions] = useState<string[]>([]);
  const [totalActions, setTotalActions] = useState(0);
  const [page, setPage] = useState(0);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedSearchQuery(searchQuery.trim());
      setPage(0);
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [searchQuery]);

  useEffect(() => {
    setPage(0);
  }, [accountFilter, regionFilter]);

  const fetchOpenActions = useCallback(async () => {
    if (!showContent) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const response = await getActions(
        {
          group_by: 'resource',
          status: 'open',
          q: debouncedSearchQuery || undefined,
          account_id: accountFilter || undefined,
          region: regionFilter || undefined,
          limit: PAGE_LIMIT,
          offset: page * PAGE_LIMIT,
        },
        effectiveTenantId
      );
      setActions(response.items);
      setTotalActions(response.total);
    } catch (err) {
      setError(getErrorMessage(err));
      setActions([]);
      setTotalActions(0);
    } finally {
      setIsLoading(false);
    }
  }, [accountFilter, debouncedSearchQuery, effectiveTenantId, page, regionFilter, showContent]);

  useEffect(() => {
    fetchOpenActions();
  }, [fetchOpenActions]);

  useEffect(() => {
    if (!showContent) return;
    let cancelled = false;

    getAccounts(effectiveTenantId)
      .then((list) => {
        if (cancelled) return;
        setAvailableAccounts(
          Array.from(new Set(list.map((account) => account.account_id))).sort()
        );
        setAvailableRegions(
          Array.from(new Set(list.flatMap((account) => account.regions || []))).sort()
        );
      })
      .catch(() => {
        if (cancelled) return;
        setAvailableAccounts([]);
        setAvailableRegions([]);
      });

    return () => {
      cancelled = true;
    };
  }, [effectiveTenantId, showContent]);

  const accountOptions = useMemo(() => {
    return availableAccounts.map((value) => ({
      value,
      label: value,
    }));
  }, [availableAccounts]);

  const regionOptions = useMemo(() => {
    return availableRegions.map((value) => ({
      value,
      label: value,
    }));
  }, [availableRegions]);

  const selectedCount = selectedIds.size;
  const totalPages = Math.max(1, Math.ceil(totalActions / PAGE_LIMIT));
  const pageStart = totalActions === 0 ? 0 : page * PAGE_LIMIT + 1;
  const pageEnd = totalActions === 0 ? 0 : Math.min(totalActions, (page + 1) * PAGE_LIMIT);

  useEffect(() => {
    if (page < totalPages) return;
    setPage(Math.max(0, totalPages - 1));
  }, [page, totalPages]);

  const toggleSelection = (actionId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(actionId)) next.delete(actionId);
      else next.add(actionId);
      return next;
    });
  };

  const selectAllFiltered = () => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (const action of actions) next.add(action.id);
      return next;
    });
  };

  const clearSelection = () => setSelectedIds(new Set());

  const goToSummary = () => {
    if (selectedIds.size === 0) return;
    const ids = Array.from(selectedIds).join(',');
    router.push(`/pr-bundles/create/summary?ids=${encodeURIComponent(ids)}`);
  };

  if (!showContent) {
    return (
      <AppShell title="Create PR Bundle">
        {!authLoading && isAuthenticated && <TenantIdForm onSave={setTenantId} />}
      </AppShell>
    );
  }

  return (
    <AppShell title="Create PR Bundle" wide>
      <div className="space-y-4">
        <DashboardHero
          eyebrow="Customer-run remediation"
          title="Generate PR bundle"
          description="Select the actions to package, review the generated plan, and move to one consistent PR-bundle workflow."
          tone="accent"
        >
          <div className="grid gap-3 md:grid-cols-3">
            <div className={remediationInsetClass('default', 'p-4')}>
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/70">Selection</p>
              <p className="mt-3 text-sm font-medium text-text">Choose open actions across accounts and regions.</p>
            </div>
            <div className={remediationInsetClass('default', 'p-4')}>
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/70">Review</p>
              <p className="mt-3 text-sm font-medium text-text">Inspect the summary before generating bundles.</p>
            </div>
            <div className={remediationInsetClass('default', 'p-4')}>
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/70">Output</p>
              <p className="mt-3 text-sm font-medium text-text">Keep the workflow dense, but make the next action obvious.</p>
            </div>
          </div>
        </DashboardHero>

        <DashboardFilterBar>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <PlaceholdersAndVanishInput
              placeholders={['Search by title, control, resource, account']}
              value={searchQuery}
              onChange={setSearchQuery}
              onSubmit={() => {}}
            />
            <SelectDropdown
              value={accountFilter}
              onValueChange={setAccountFilter}
              options={[{ value: '', label: 'All accounts' }, ...accountOptions]}
              aria-label="Filter by account"
            />
            <SelectDropdown
              value={regionFilter}
              onValueChange={setRegionFilter}
              options={[{ value: '', label: 'All regions' }, ...regionOptions]}
              aria-label="Filter by region"
            />
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={selectAllFiltered} disabled={actions.length === 0}>
              Select filtered
            </Button>
            <Button variant="ghost" onClick={clearSelection} disabled={selectedCount === 0}>
              Clear selection
            </Button>
            <Button variant="primary" onClick={goToSummary} disabled={selectedCount === 0}>
              Review bundle ({selectedCount})
            </Button>
            <div className="ml-auto text-xs text-muted">
              {isLoading ? 'Loading results…' : `Showing ${pageStart}-${pageEnd} of ${totalActions}`}
            </div>
          </div>
        </DashboardFilterBar>

        {error && (
          <div className={remediationInsetClass('danger', 'p-3 text-sm text-danger')}>
            {error}
          </div>
        )}

        <DashboardTableCard>
          <table className="w-full text-sm">
            <thead className="bg-[var(--card-inset)]">
              <tr className="text-left text-muted">
                <th className="px-4 py-3">Pick</th>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Control</th>
                <th className="px-4 py-3">Account</th>
                <th className="px-4 py-3">Region</th>
                <th className="px-4 py-3">Matrix</th>
                <th className="px-4 py-3">Findings</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td className="px-4 py-6 text-muted" colSpan={7}>
                    Loading actions...
                  </td>
                </tr>
              )}
              {!isLoading && actions.length === 0 && (
                <tr>
                  <td className="px-4 py-6 text-muted" colSpan={7}>
                    No matching open actions.
                  </td>
                </tr>
              )}
              {!isLoading &&
                actions.map((action) => {
                  const checked = selectedIds.has(action.id);
                  return (
                    <tr key={action.id} className="border-t border-border/60">
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleSelection(action.id)}
                          aria-label={`Select action ${action.id}`}
                          className="h-4 w-4"
                        />
                      </td>
                      <td className="px-4 py-3 text-text">{action.title}</td>
                      <td className="px-4 py-3 font-mono text-muted">{action.control_id || '—'}</td>
                      <td className="px-4 py-3 font-mono text-muted">{action.account_id}</td>
                      <td className="px-4 py-3 font-mono text-muted">{action.region || 'global'}</td>
                      <td className="px-4 py-3">
                        <div className="text-text">{formatMatrixLabel(action)}</div>
                        <div className="text-xs text-muted">
                          {titleCaseToken(action.business_impact.criticality.status === 'unknown'
                            ? 'unknown criticality'
                            : action.business_impact.criticality.tier)}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-text">{action.finding_count}</td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-border/50 px-4 py-3">
            <p className="text-xs text-muted">
              Filtered results stay server-backed to keep the table responsive while selection persists locally.
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                onClick={() => setPage((current) => Math.max(0, current - 1))}
                disabled={page === 0 || isLoading}
              >
                Previous
              </Button>
              <span className="text-xs text-muted">
                Page {Math.min(page + 1, totalPages)} of {totalPages}
              </span>
              <Button
                variant="ghost"
                onClick={() => setPage((current) => Math.min(totalPages - 1, current + 1))}
                disabled={page >= totalPages - 1 || isLoading}
              >
                Next
              </Button>
            </div>
          </div>
        </DashboardTableCard>
      </div>
    </AppShell>
  );
}
