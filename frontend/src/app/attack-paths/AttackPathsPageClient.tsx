'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

import { AppShell } from '@/components/layout';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  ActionAttackPathDetail,
  AttackPathSummaryItem,
  AttackPathViewOption,
  getAttackPath,
  getAttackPaths,
  getErrorMessage,
} from '@/lib/api';
import { useTenantId } from '@/lib/tenant';

type AttackPathStatus = AttackPathSummaryItem['status'] | '';

function statusVariant(status: AttackPathSummaryItem['status']): 'success' | 'warning' | 'info' {
  if (status === 'available') return 'success';
  if (status === 'partial') return 'warning';
  return 'info';
}

function formatNodes(items: { label: string }[]): string {
  if (!items.length) return 'Not resolved';
  return items.map((item) => item.label).join(' -> ');
}

function formatPathHref(params: {
  accountId: string;
  actionId: string;
  ownerKey: string;
  resourceId: string;
  status: AttackPathStatus;
  view: string;
  pathId?: string | null;
}): string {
  const query = new URLSearchParams();
  if (params.accountId) query.set('account_id', params.accountId);
  if (params.actionId) query.set('action_id', params.actionId);
  if (params.ownerKey) query.set('owner_key', params.ownerKey);
  if (params.resourceId) query.set('resource_id', params.resourceId);
  if (params.status) query.set('status', params.status);
  if (params.view) query.set('view', params.view);
  if (params.pathId) query.set('path_id', params.pathId);
  return query.toString() ? `/attack-paths?${query.toString()}` : '/attack-paths';
}

function formatOwnerLabels(items: { owner_label?: string }[]): string {
  const labels = items.map((item) => item.owner_label).filter((label): label is string => Boolean(label));
  return labels.length ? labels.join(', ') : 'Unassigned';
}

function formatRankFactor(factor: {
  label?: string;
  factor_name?: string;
  explanation?: string;
  contribution?: number;
}): string {
  const label = factor.label ?? factor.factor_name ?? 'Rank factor';
  const contribution =
    factor.contribution === undefined ? '' : ` (${factor.contribution >= 0 ? '+' : ''}${factor.contribution})`;
  const explanation = factor.explanation ? ` - ${factor.explanation}` : '';
  return `${label}${contribution}${explanation}`;
}

function formatEvidence(items: { label?: string; value?: string; source?: string }[]): string[] {
  return items
    .map((item) => [item.label, item.value, item.source].filter(Boolean).join(': '))
    .filter((value) => value.length > 0);
}

function formatFreshness(summary?: AttackPathSummaryItem['freshness'] | ActionAttackPathDetail['freshness'] | null): string {
  if (!summary) return 'Freshness not available yet.';
  if (summary.summary) return summary.summary;
  if (summary.observed_at) return `Observed at ${summary.observed_at}`;
  return 'Freshness available';
}

export default function AttackPathsPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { tenantId } = useTenantId();
  const searchKey = searchParams.toString();

  const [accountId, setAccountId] = useState(searchParams.get('account_id') ?? '');
  const [actionId, setActionId] = useState(searchParams.get('action_id') ?? '');
  const [ownerKey, setOwnerKey] = useState(searchParams.get('owner_key') ?? '');
  const [resourceId, setResourceId] = useState(searchParams.get('resource_id') ?? '');
  const [status, setStatus] = useState<AttackPathStatus>((searchParams.get('status') as AttackPathStatus) ?? '');
  const [view, setView] = useState(searchParams.get('view') ?? '');
  const [pathId, setPathId] = useState(searchParams.get('path_id') ?? '');

  const [items, setItems] = useState<AttackPathSummaryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [availableViews, setAvailableViews] = useState<AttackPathViewOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedPathDetail, setSelectedPathDetail] = useState<ActionAttackPathDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const selectedPathSummary = useMemo(
    () => items.find((item) => item.id === pathId) ?? null,
    [items, pathId],
  );
  const selectedConfidence = selectedPathDetail?.confidence ?? selectedPathSummary?.confidence ?? 0;
  const selectedSummaryHasNodes = Boolean(
    selectedPathSummary?.entry_points.length || selectedPathSummary?.target_assets.length,
  );

  useEffect(() => {
    setAccountId(searchParams.get('account_id') ?? '');
    setActionId(searchParams.get('action_id') ?? '');
    setOwnerKey(searchParams.get('owner_key') ?? '');
    setResourceId(searchParams.get('resource_id') ?? '');
    setStatus((searchParams.get('status') as AttackPathStatus) ?? '');
    setView(searchParams.get('view') ?? '');
    setPathId(searchParams.get('path_id') ?? '');
  }, [searchKey]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setListError(null);
    getAttackPaths(
      {
        account_id: accountId || undefined,
        action_id: actionId || undefined,
        owner_key: ownerKey || undefined,
        resource_id: resourceId || undefined,
        status: status || undefined,
        view: view || undefined,
        limit: 10,
        offset: 0,
      },
      tenantId ?? undefined,
    )
      .then((response) => {
        if (!active) return;
        setItems(response.items);
        setTotal(response.total);
        setAvailableViews(response.available_views ?? []);
        setPathId((current) => current || response.items[0]?.id || '');
      })
      .catch((loadError) => {
        if (!active) return;
        setListError(getErrorMessage(loadError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [accountId, actionId, ownerKey, resourceId, status, tenantId, view]);

  useEffect(() => {
    if (!pathId) {
      setSelectedPathDetail(null);
      setDetailError(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    setDetailError(null);
    getAttackPath(pathId, tenantId ?? undefined)
      .then((payload) => {
        if (active) setSelectedPathDetail(payload);
      })
      .catch((loadError) => {
        if (!active) return;
        setSelectedPathDetail(null);
        setDetailError(getErrorMessage(loadError));
      })
      .finally(() => {
        if (active) setDetailLoading(false);
      });

    return () => {
      active = false;
    };
  }, [pathId, tenantId]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = new URLSearchParams();
    if (accountId) params.set('account_id', accountId);
    if (actionId) params.set('action_id', actionId);
    if (ownerKey) params.set('owner_key', ownerKey);
    if (resourceId) params.set('resource_id', resourceId);
    if (status) params.set('status', status);
    if (view) params.set('view', view);
    if (pathId) params.set('path_id', pathId);
    router.replace(params.toString() ? `/attack-paths?${params.toString()}` : '/attack-paths');
  }

  const selectedStatus = selectedPathDetail?.status ?? selectedPathSummary?.status ?? 'available';
  const selectedRank = selectedPathDetail?.rank ?? selectedPathSummary?.rank ?? 0;
  const selectedSummary = selectedPathDetail?.summary ?? selectedPathSummary?.summary ?? 'Shared attack path detail is unavailable.';
  const selectedBusinessImpact =
    selectedPathDetail?.business_impact?.summary ?? selectedPathSummary?.business_impact_summary ?? null;
  const selectedFix =
    selectedPathDetail?.recommended_fix?.summary ?? selectedPathSummary?.recommended_fix_summary ?? null;
  const selectedOwners = selectedPathDetail?.owners?.length
    ? formatOwnerLabels(selectedPathDetail.owners)
    : selectedPathSummary?.owner_labels.join(', ') || 'Unassigned';
  const selectedLinkedActionIds = selectedPathDetail?.linked_actions?.length
    ? selectedPathDetail.linked_actions.map((item) => item.id)
    : selectedPathSummary?.linked_action_ids ?? [];
  const selectedRankFactors = selectedPathDetail?.rank_factors ?? [];
  const selectedRiskReasons = selectedPathDetail?.risk_reasons ?? [];
  const selectedEvidence = formatEvidence(selectedPathDetail?.evidence ?? []);
  const selectedProvenance = formatEvidence(selectedPathDetail?.provenance ?? []);
  const selectedRemediation = selectedPathDetail?.remediation_summary ?? selectedPathSummary?.remediation_summary ?? null;
  const selectedFreshness = selectedPathDetail?.freshness ?? selectedPathSummary?.freshness ?? null;
  const selectedRuntimeSignals = selectedPathDetail?.runtime_signals ?? selectedPathSummary?.runtime_signals ?? null;
  const selectedClosureTargets = selectedPathDetail?.closure_targets ?? selectedPathSummary?.closure_targets ?? null;
  const selectedGovernance = selectedPathDetail?.external_workflow_summary ?? selectedPathSummary?.governance_summary ?? null;
  const selectedAccessScope = selectedPathDetail?.access_scope ?? selectedPathSummary?.access_scope ?? null;

  return (
    <AppShell title="Attack Paths">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">Phase 2</p>
              <h1 className="mt-2 text-3xl font-semibold text-text">Attack Paths</h1>
              <p className="mt-3 max-w-3xl text-sm text-muted">
                Ranked, tenant-scoped attack stories sourced from the persisted security graph. The list stays bounded
                and triage-focused while the selected path opens a shared detail record.
              </p>
            </div>
            <div className="rounded-xl border border-border/70 bg-muted/20 px-4 py-3 text-right">
              <p className="text-xs uppercase tracking-[0.2em] text-muted">Paths</p>
              <p className="mt-1 text-2xl font-semibold text-text">{total}</p>
            </div>
          </div>
          <form className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-5" onSubmit={applyFilters}>
            <Input value={accountId} onChange={(event) => setAccountId(event.target.value)} placeholder="Account ID" />
            <Input value={actionId} onChange={(event) => setActionId(event.target.value)} placeholder="Action ID" />
            <Input value={ownerKey} onChange={(event) => setOwnerKey(event.target.value)} placeholder="Owner key" />
            <Input value={resourceId} onChange={(event) => setResourceId(event.target.value)} placeholder="Resource ID" />
            <select
              aria-label="Attack path status"
              className="rounded-xl border border-border bg-background px-3 py-2 text-sm text-text"
              value={status}
              onChange={(event) => setStatus(event.target.value as AttackPathStatus)}
            >
              <option value="">All statuses</option>
              <option value="available">Available</option>
              <option value="partial">Partial</option>
              <option value="unavailable">Unavailable</option>
              <option value="context_incomplete">Context incomplete</option>
            </select>
            <div className="md:col-span-5 flex gap-3">
              <Button type="submit">Apply filters</Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setAccountId('');
                  setActionId('');
                  setOwnerKey('');
                  setResourceId('');
                  setStatus('');
                  setView('');
                  setPathId('');
                  router.replace('/attack-paths');
                }}
              >
                Reset
              </Button>
            </div>
          </form>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              type="button"
              variant={view ? 'secondary' : 'primary'}
              onClick={() => {
                setView('');
                router.replace(formatPathHref({ accountId, actionId, ownerKey, resourceId, status, view: '', pathId }));
              }}
            >
              All paths
            </Button>
            {availableViews.map((option) => (
              <Button
                key={option.key}
                type="button"
                variant={view === option.key ? 'primary' : 'secondary'}
                onClick={() => {
                  setView(option.key);
                  router.replace(formatPathHref({ accountId, actionId, ownerKey, resourceId, status, view: option.key, pathId }));
                }}
              >
                {option.label}
              </Button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.3fr_0.9fr]">
          <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-text">Ranked paths</h2>
              {loading && <span className="text-sm text-muted">Loading…</span>}
            </div>
            {listError && <p className="rounded-xl border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">{listError}</p>}
            {!loading && !listError && !items.length && (
              <p className="rounded-xl border border-border/70 bg-muted/20 px-4 py-6 text-sm text-muted">
                No attack paths matched the current filters.
              </p>
            )}
            <div className="space-y-3">
              {items.map((item) => (
                <Link
                  key={item.id}
                  href={formatPathHref({
                    accountId,
                    actionId,
                    ownerKey,
                    resourceId,
                    status,
                    view,
                    pathId: item.id,
                  })}
                  onClick={() => setPathId(item.id)}
                  className={`block w-full rounded-2xl border p-4 text-left transition-colors ${
                    selectedPathSummary?.id === item.id
                      ? 'border-accent bg-accent/5'
                      : 'border-border bg-background hover:border-accent/40'
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={statusVariant(item.status)}>{item.status.replace(/_/g, ' ')}</Badge>
                    <Badge variant="info">Rank {item.rank}</Badge>
                    <span className="text-xs uppercase tracking-[0.16em] text-muted">
                      Confidence {Math.round(item.confidence * 100)}%
                    </span>
                  </div>
                  <p className="mt-3 text-sm font-medium leading-6 text-text">{item.summary}</p>
                  <p className="mt-3 text-xs uppercase tracking-[0.16em] text-muted">
                    Entry: {formatNodes(item.entry_points)} | Target: {formatNodes(item.target_assets)}
                  </p>
                  <p className="mt-3 text-sm text-muted">Owners: {item.owner_labels.join(', ') || 'Unassigned'}</p>
                  <p className="mt-2 text-sm text-muted">{formatFreshness(item.freshness)}</p>
                  {item.remediation_summary && (
                    <p className="mt-2 text-sm text-muted">{item.remediation_summary.coverage_summary}</p>
                  )}
                  {item.runtime_signals && (
                    <p className="mt-2 text-sm text-muted">{item.runtime_signals.summary}</p>
                  )}
                  {item.governance_summary && (
                    <p className="mt-2 text-sm text-muted">{item.governance_summary.summary}</p>
                  )}
                </Link>
              ))}
            </div>
          </section>

          <aside className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-text">Path detail</h2>
            {!pathId && !loading && <p className="mt-4 text-sm text-muted">Select a path to inspect the shared path detail.</p>}
            {pathId && (
              <div className="mt-4 space-y-4">
                <div className="rounded-xl border border-border bg-background p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={statusVariant(selectedStatus)}>{selectedStatus.replace(/_/g, ' ')}</Badge>
                    <Badge variant="info">Rank {selectedRank}</Badge>
                    <span className="text-xs uppercase tracking-[0.16em] text-muted">
                      Confidence {Math.round(selectedConfidence * 100)}%
                    </span>
                  </div>
                  {detailLoading && <p className="mt-3 text-sm text-muted">Loading path detail…</p>}
                  {detailError && <p className="mt-3 text-sm text-danger">{detailError}</p>}
                  {!detailLoading && !detailError && (
                    <>
                      <p className="mt-3 text-sm leading-6 text-text">{selectedSummary}</p>
                      {selectedBusinessImpact && <p className="mt-3 text-sm text-muted">{selectedBusinessImpact}</p>}
                      {selectedFix && <p className="mt-3 text-sm font-medium text-accent">{selectedFix}</p>}
                    </>
                  )}
                </div>

                <div className="rounded-xl border border-border bg-background p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted">Runtime truth</p>
                  <div className="mt-3 space-y-2 text-sm text-text">
                    {selectedRuntimeSignals ? (
                      <>
                        <p className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">{selectedRuntimeSignals.summary}</p>
                        <p className="text-muted">
                          Publicly reachable: {selectedRuntimeSignals.publicly_reachable ? 'Yes' : 'No'} | Sensitive targets: {selectedRuntimeSignals.sensitive_target_count} | Identity hops: {selectedRuntimeSignals.identity_hops}
                        </p>
                      </>
                    ) : (
                      <p className="text-muted">No runtime truth summary returned yet.</p>
                    )}
                    {selectedPathDetail?.exposure_validation && (
                      <p className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">
                        {selectedPathDetail.exposure_validation.summary}
                      </p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border bg-background p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted">Rank factors</p>
                  <div className="mt-3 space-y-2 text-sm text-text">
                    {selectedRankFactors.length ? (
                      selectedRankFactors.map((factor, index) => (
                        <p key={`${factor.factor_name ?? factor.label ?? 'factor'}-${index}`} className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">
                          {formatRankFactor(factor)}
                        </p>
                      ))
                    ) : (
                      <p className="text-muted">No rank factors returned yet.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border bg-background p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted">Code to cloud</p>
                  <div className="mt-3 space-y-2 text-sm text-text">
                    {selectedPathDetail?.code_context ? (
                      <>
                        <p className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">
                          {selectedPathDetail.code_context.summary}
                        </p>
                        {selectedPathDetail.linked_repositories?.length ? (
                          selectedPathDetail.linked_repositories.map((repo) => (
                            <p key={`${repo.provider}-${repo.repository}-${repo.source_run_id ?? ''}`} className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">
                              {repo.repository}
                              {repo.base_branch ? ` -> ${repo.base_branch}` : ''}
                              {repo.root_path ? ` (${repo.root_path})` : ''}
                            </p>
                          ))
                        ) : (
                          <p className="text-muted">No repo-aware target returned yet.</p>
                        )}
                      </>
                    ) : (
                      <p className="text-muted">No code-to-cloud linkage returned yet.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border bg-background p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted">Linked actions</p>
                  {selectedRemediation && (
                    <div className="mt-3 rounded-lg border border-border/70 bg-surface/60 px-3 py-3 text-sm text-text">
                      <p>{selectedRemediation.coverage_summary}</p>
                      <p className="mt-2 text-muted">
                        Open {selectedRemediation.open_actions} | In progress {selectedRemediation.in_progress_actions} | Resolved {selectedRemediation.resolved_actions}
                      </p>
                    </div>
                  )}
                  {selectedClosureTargets && (
                    <p className="mt-3 text-sm text-muted">{selectedClosureTargets.summary}</p>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedLinkedActionIds.length ? (
                      selectedLinkedActionIds.map((linkedActionId) => (
                        <Link
                          key={linkedActionId}
                          href={`/actions/${linkedActionId}`}
                          className="rounded-lg border border-border px-3 py-1.5 text-sm text-text transition-colors hover:border-accent hover:text-accent"
                        >
                          {linkedActionId}
                        </Link>
                      ))
                    ) : (
                      <p className="text-sm text-muted">No linked actions returned yet.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border bg-background p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted">Path evidence</p>
                  <div className="mt-3 space-y-2 text-sm text-text">
                    {selectedRiskReasons.length ? (
                      selectedRiskReasons.map((reason) => (
                        <p key={reason} className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">
                          {reason}
                        </p>
                      ))
                    ) : (
                      <p className="text-muted">No risk reasons returned yet.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border bg-background p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted">Nodes</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedPathDetail?.path_nodes?.length ? (
                      selectedPathDetail.path_nodes.map((node) => (
                        <span
                          key={node.node_id}
                          className="rounded-full border border-border px-3 py-1 text-xs uppercase tracking-[0.14em] text-muted"
                        >
                          {node.label}
                        </span>
                      ))
                    ) : selectedSummaryHasNodes ? (
                      <>
                        {selectedPathSummary!.entry_points.map((node) => (
                          <span
                            key={node.node_id}
                            className="rounded-full border border-border px-3 py-1 text-xs uppercase tracking-[0.14em] text-muted"
                          >
                            {node.label}
                          </span>
                        ))}
                        {selectedPathSummary!.target_assets.map((node) => (
                          <span
                            key={node.node_id}
                            className="rounded-full border border-border px-3 py-1 text-xs uppercase tracking-[0.14em] text-muted"
                          >
                            {node.label}
                          </span>
                        ))}
                      </>
                    ) : (
                      <p className="text-sm text-muted">No bounded path nodes returned yet.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border bg-background p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted">Freshness and provenance</p>
                  <div className="mt-3 space-y-2 text-sm text-text">
                    {selectedFreshness ? (
                      <p className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">
                        {formatFreshness(selectedFreshness)}
                      </p>
                    ) : (
                      <p className="text-muted">No freshness summary returned yet.</p>
                    )}
                    {selectedEvidence.length > 0 && (
                      <div className="space-y-2">
                        {selectedEvidence.map((item) => (
                          <p key={item} className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">
                            {item}
                          </p>
                        ))}
                      </div>
                    )}
                    {selectedProvenance.length > 0 && (
                      <div className="space-y-2">
                        {selectedProvenance.map((item) => (
                          <p key={item} className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">
                            {item}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border bg-background p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted">Owners</p>
                  <p className="mt-3 text-sm text-text">{selectedOwners}</p>
                </div>

                <div className="rounded-xl border border-border bg-background p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted">Workflow controls</p>
                  <div className="mt-3 space-y-2 text-sm text-text">
                    {selectedGovernance ? (
                      <p className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">{selectedGovernance.summary}</p>
                    ) : (
                      <p className="text-muted">No external workflow summary returned yet.</p>
                    )}
                    {selectedPathDetail?.exception_summary && (
                      <p className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">
                        {selectedPathDetail.exception_summary.summary}
                      </p>
                    )}
                    {selectedPathDetail?.evidence_exports && (
                      <p className="rounded-lg border border-border/70 bg-surface/60 px-3 py-2">
                        {selectedPathDetail.evidence_exports.summary}
                      </p>
                    )}
                    {selectedAccessScope && (
                      <p className="text-muted">
                        Scope: {selectedAccessScope.scope.replace(/_/g, ' ')} | Evidence visibility: {selectedAccessScope.evidence_visibility}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
