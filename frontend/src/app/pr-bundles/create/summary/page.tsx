'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { TenantIdForm } from '@/components/TenantIdForm';
import {
  RemediationCallout,
  RemediationSection,
  RemediationStatCard,
  remediationInsetClass,
  remediationTableWrapperClass,
} from '@/components/ui/remediation-surface';
import { useAuth } from '@/contexts/AuthContext';
import { useTenantId } from '@/lib/tenant';
import {
  ActionListItem,
  createGroupPrBundleRun,
  createRemediationRun,
  getActions,
  getErrorMessage,
  getRemediationOptions,
} from '@/lib/api';
import { deriveAutoPrOnlySelection } from '@/lib/remediationAutoSelection';

export const dynamic = 'force-dynamic';

const IDS_CHUNK_SIZE = 100;

const ACTION_COST_WEIGHTS: Record<string, number> = {
  s3_bucket_block_public_access: 3,
  s3_migrate_cloudfront_oac_private: 5,
  cloudtrail_enabled: 4,
  aws_config_enabled: 4,
  enable_security_hub: 2,
  enable_guardduty: 2,
};

type GenerateResult = {
  succeeded: string[];
  failed: { actionId: string; message: string }[];
};

type ExecutionGroup = {
  key: string;
  action_type: string;
  account_id: string;
  status: 'open' | 'in_progress' | 'resolved' | 'suppressed';
  region: string | null;
  actionCount: number;
  actionIds: string[];
  targetIds: string[];
  estimatedCost: number;
};

type ExecutionLane = {
  index: number;
  groups: ExecutionGroup[];
  cost: number;
};

type ActionPreflightResult =
  | {
      ok: true;
      actionId: string;
      strategyId?: string;
      strategyInputs: Record<string, unknown>;
    }
  | {
      ok: false;
      actionId: string;
      message: string;
    };

type GroupPreflightResult =
  | {
      ok: true;
      strategyId?: string;
      strategyInputs: Record<string, unknown>;
    }
  | {
      ok: false;
      message: string;
    };

function actionWeight(actionType: string): number {
  return ACTION_COST_WEIGHTS[actionType] ?? 2;
}

function titleCaseToken(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function isValidIpv4Address(value: string): boolean {
  const octets = value.split('.');
  if (octets.length !== 4) return false;
  return octets.every((segment) => {
    if (!/^\d{1,3}$/.test(segment)) return false;
    const numeric = Number(segment);
    return numeric >= 0 && numeric <= 255;
  });
}

function normalizeComparableValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeComparableValue(item));
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right));
    return Object.fromEntries(entries.map(([key, item]) => [key, normalizeComparableValue(item)]));
  }
  return value;
}

function stableComparableKey(value: unknown): string {
  return JSON.stringify(normalizeComparableValue(value));
}

function hasStrategyInputs(values: Record<string, unknown>): boolean {
  return Object.keys(values).length > 0;
}

function groupBlockedMessage(results: Extract<ActionPreflightResult, { ok: false }>[]): string {
  return results.map((item) => `${item.actionId}: ${item.message}`).join(' | ');
}

function groupStrategyMismatchMessage(results: Extract<ActionPreflightResult, { ok: true }>[]): string {
  return results
    .map((item) => `${item.actionId}: ${item.strategyId ?? '(none)'}`)
    .join(' | ');
}

function planGroupGeneration(
  group: ExecutionGroup,
  resultsByActionId: Map<string, ActionPreflightResult>,
): GroupPreflightResult {
  const results = group.actionIds
    .map((actionId) => resultsByActionId.get(actionId))
    .filter((item): item is ActionPreflightResult => Boolean(item));
  const blocked = results.filter((item): item is Extract<ActionPreflightResult, { ok: false }> => !item.ok);
  if (blocked.length > 0) return { ok: false, message: groupBlockedMessage(blocked) };
  const successful = results.filter((item): item is Extract<ActionPreflightResult, { ok: true }> => item.ok);
  const strategyKeys = new Set(successful.map((item) => item.strategyId ?? ''));
  if (strategyKeys.size > 1) {
    return { ok: false, message: `Auto-selected strategies differ across grouped actions. ${groupStrategyMismatchMessage(successful)}` };
  }
  const inputKeys = new Set(successful.map((item) => stableComparableKey(item.strategyInputs)));
  if (inputKeys.size > 1) {
    return { ok: false, message: `Auto-derived strategy inputs differ across grouped actions: ${group.actionIds.join(', ')}` };
  }
  return successful[0] ?? { ok: true, strategyInputs: {} };
}

function formatMatrixLabel(action: ActionListItem): string {
  const risk = titleCaseToken(action.business_impact.technical_risk_tier);
  const criticality = titleCaseToken(action.business_impact.criticality.tier);
  return `${risk} x ${criticality}`;
}

function partitionExecutionGroups(groups: ExecutionGroup[], requestedParallelism: number): ExecutionLane[] {
  const laneCount = Math.max(1, Math.min(requestedParallelism, groups.length || 1));
  const lanes: ExecutionLane[] = Array.from({ length: laneCount }, (_, idx) => ({
    index: idx,
    groups: [],
    cost: 0,
  }));
  const targetLaneByTargetId = new Map<string, number>();

  const sorted = [...groups].sort((a, b) => {
    if (b.estimatedCost !== a.estimatedCost) return b.estimatedCost - a.estimatedCost;
    if (b.actionCount !== a.actionCount) return b.actionCount - a.actionCount;
    return a.key.localeCompare(b.key);
  });

  for (const group of sorted) {
    const preferredLaneCandidates = new Set<number>();
    for (const targetId of group.targetIds) {
      const existingLane = targetLaneByTargetId.get(targetId);
      if (existingLane !== undefined) preferredLaneCandidates.add(existingLane);
    }

    let selectedLane = -1;
    if (preferredLaneCandidates.size > 0) {
      selectedLane = Math.min(...Array.from(preferredLaneCandidates));
    } else {
      const sameAccountRegionLanes = lanes.filter((lane) =>
        lane.groups.some(
          (existing) => existing.account_id === group.account_id && (existing.region || 'global') === (group.region || 'global')
        )
      );
      if (sameAccountRegionLanes.length > 0) {
        selectedLane = sameAccountRegionLanes.sort((a, b) => a.cost - b.cost)[0].index;
      } else {
        selectedLane = lanes.sort((a, b) => a.cost - b.cost)[0].index;
      }
    }

    lanes[selectedLane].groups.push(group);
    lanes[selectedLane].cost += group.estimatedCost;
    for (const targetId of group.targetIds) {
      targetLaneByTargetId.set(targetId, selectedLane);
    }
  }

  return lanes.filter((lane) => lane.groups.length > 0);
}

async function runWithConcurrency<T, R>(
  items: T[],
  concurrency: number,
  worker: (item: T) => Promise<R>
): Promise<R[]> {
  const limit = Math.max(1, concurrency);
  const results: R[] = new Array(items.length);
  let cursor = 0;

  async function runOne(): Promise<void> {
    while (cursor < items.length) {
      const idx = cursor;
      cursor += 1;
      results[idx] = await worker(items[idx]);
    }
  }

  const runners = Array.from({ length: Math.min(limit, items.length) }, () => runOne());
  await Promise.all(runners);
  return results;
}

function PrBundleSummaryPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { tenantId, setTenantId } = useTenantId();
  const effectiveTenantId = isAuthenticated ? undefined : tenantId;
  const showContent = isAuthenticated || Boolean(tenantId);
  const selectedIdsParam = searchParams.get('ids') || '';

  const selectedIds = useMemo(() => {
    const raw = selectedIdsParam.trim();
    if (!raw) return new Set<string>();
    return new Set(raw.split(',').map((id) => decodeURIComponent(id.trim())).filter(Boolean));
  }, [selectedIdsParam]);

  const [selectedActions, setSelectedActions] = useState<ActionListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [parallelCount, setParallelCount] = useState(3);
  const [generatedRunIds, setGeneratedRunIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [detectedPublicIpv4Cidr, setDetectedPublicIpv4Cidr] = useState<string | null>(null);

  const fetchActionsForSummary = useCallback(async () => {
    if (!showContent) {
      setIsLoading(false);
      return;
    }
    if (selectedIds.size === 0) {
      setSelectedActions([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const idList = Array.from(selectedIds);
      const chunks: string[][] = [];
      for (let index = 0; index < idList.length; index += IDS_CHUNK_SIZE) {
        chunks.push(idList.slice(index, index + IDS_CHUNK_SIZE));
      }

      const responses = await Promise.all(
        chunks.map((chunk) =>
          getActions(
            {
              group_by: 'resource',
              ids: chunk,
              limit: chunk.length,
            },
            effectiveTenantId
          )
        )
      );

      const ordered = new Map<string, ActionListItem>();
      responses.forEach((response) => {
        response.items.forEach((action) => {
          ordered.set(action.id, action);
        });
      });
      setSelectedActions(idList.map((id) => ordered.get(id)).filter((action): action is ActionListItem => Boolean(action)));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [showContent, effectiveTenantId, selectedIds]);

  useEffect(() => {
    fetchActionsForSummary();
  }, [fetchActionsForSummary]);

  useEffect(() => {
    let cancelled = false;

    fetch('https://api.ipify.org?format=json')
      .then(async (response) => {
        if (!response.ok) return null;
        const payload = (await response.json()) as { ip?: unknown };
        return typeof payload.ip === 'string' ? payload.ip.trim() : null;
      })
      .then((ip) => {
        if (cancelled || !ip || !isValidIpv4Address(ip)) return;
        setDetectedPublicIpv4Cidr(`${ip}/32`);
      })
      .catch(() => {
        // Best-effort only; safe-default auto-fill remains conservative when lookup fails.
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const totals = useMemo(() => {
    const findingCount = selectedActions.reduce((sum, action) => sum + (action.finding_count || 0), 0);
    const byAccount = new Map<string, number>();
    const byMatrix = new Map<string, number>();
    const byRegion = new Map<string, number>();
    const byType = new Map<string, number>();

    for (const action of selectedActions) {
      byAccount.set(action.account_id, (byAccount.get(action.account_id) || 0) + 1);
      byMatrix.set(formatMatrixLabel(action), (byMatrix.get(formatMatrixLabel(action)) || 0) + 1);
      byRegion.set(action.region || 'global', (byRegion.get(action.region || 'global') || 0) + 1);
      byType.set(action.action_type, (byType.get(action.action_type) || 0) + 1);
    }

    return {
      actionCount: selectedActions.length,
      findingCount,
      byAccount: Array.from(byAccount.entries()),
      byMatrix: Array.from(byMatrix.entries()),
      byRegion: Array.from(byRegion.entries()),
      byType: Array.from(byType.entries()),
    };
  }, [selectedActions]);

  const executionGroups = useMemo(() => {
    const grouped = new Map<string, ExecutionGroup>();
    for (const action of selectedActions) {
      const status = ((action.status || 'open').toLowerCase() as ExecutionGroup['status']);
      const key = `${action.action_type}|${action.account_id}|${action.region || 'global'}|${status}`;
      const existing = grouped.get(key);
      if (existing) {
        existing.actionCount += 1;
        existing.actionIds.push(action.id);
        existing.targetIds.push(action.target_id);
        existing.estimatedCost += actionWeight(action.action_type);
      } else {
        grouped.set(key, {
          key,
          action_type: action.action_type,
          account_id: action.account_id,
          region: action.region || null,
          status,
          actionCount: 1,
          actionIds: [action.id],
          targetIds: [action.target_id],
          estimatedCost: actionWeight(action.action_type),
        });
      }
    }

    return Array.from(grouped.values()).map((group) => ({
      ...group,
      actionIds: Array.from(new Set(group.actionIds)).sort(),
      targetIds: Array.from(new Set(group.targetIds)).sort(),
    }));
  }, [selectedActions]);

  const executionLanes = useMemo(
    () => partitionExecutionGroups(executionGroups, parallelCount),
    [executionGroups, parallelCount]
  );

  const buildPreflightPlan = useCallback(
    async (action: ActionListItem): Promise<ActionPreflightResult> => {
      try {
        const options = await getRemediationOptions(action.id, effectiveTenantId);
        const selection = deriveAutoPrOnlySelection(options, action.account_id, action.region, detectedPublicIpv4Cidr);
        if (!selection.ok) {
          return { ok: false, actionId: action.id, message: selection.message };
        }
        return {
          ok: true,
          actionId: action.id,
          strategyId: selection.strategyId,
          strategyInputs: selection.strategyInputs,
        };
      } catch (err) {
        return { ok: false, actionId: action.id, message: getErrorMessage(err) };
      }
    },
    [detectedPublicIpv4Cidr, effectiveTenantId],
  );

  const handleGenerate = async () => {
    if (selectedActions.length === 0) return;
    setIsGenerating(true);
    setError(null);
    setResult(null);
    setGeneratedRunIds([]);

    const succeeded: string[] = [];
    const failed: { actionId: string; message: string }[] = [];

    try {
      const preflightResults = await runWithConcurrency(
        selectedActions,
        Math.max(1, parallelCount),
        buildPreflightPlan,
      );
      const resultsByActionId = new Map(preflightResults.map((item) => [item.actionId, item]));

      if (selectedActions.length > 1) {
        const groups = executionGroups;
        const generationResults = await runWithConcurrency(groups, Math.max(1, parallelCount), async (group) => {
          const plan = planGroupGeneration(group, resultsByActionId);
          if (!plan.ok) {
            return { ok: false as const, key: group.key, message: plan.message };
          }
          try {
            const run = await createGroupPrBundleRun(
              {
                action_type: group.action_type,
                account_id: group.account_id,
                status: group.status,
                ...(group.region ? { region: group.region } : { region_is_null: true }),
                ...(plan.strategyId ? { strategy_id: plan.strategyId } : {}),
                ...(hasStrategyInputs(plan.strategyInputs) ? { strategy_inputs: plan.strategyInputs } : {}),
              },
              effectiveTenantId,
            );
            return { ok: true as const, runId: run.id, key: group.key };
          } catch (err) {
            return { ok: false as const, key: group.key, message: getErrorMessage(err) };
          }
        });

        generationResults.forEach((item) => {
          if (item.ok) {
            succeeded.push(item.runId);
          } else {
            failed.push({ actionId: item.key, message: item.message });
          }
        });
      } else {
        const action = selectedActions[0];
        const plan = resultsByActionId.get(action.id);
        if (!plan || !plan.ok) {
          failed.push({ actionId: action.id, message: plan?.message ?? 'Remediation preflight failed.' });
        } else {
          try {
            const run = await createRemediationRun(
              action.id,
              'pr_only',
              effectiveTenantId,
              plan.strategyId,
              hasStrategyInputs(plan.strategyInputs) ? plan.strategyInputs : undefined,
            );
            succeeded.push(run.id);
          } catch (err) {
            failed.push({ actionId: action.id, message: getErrorMessage(err) });
          }
        }
      }
    } finally {
      setGeneratedRunIds(succeeded);
      setResult({ succeeded, failed });
      setIsGenerating(false);
    }
  };

  if (!showContent) {
    return (
      <AppShell title="PR Bundle Summary">
        {!authLoading && isAuthenticated && <TenantIdForm onSave={setTenantId} />}
      </AppShell>
    );
  }

  return (
    <AppShell title="PR Bundle Summary" wide>
      <div className="space-y-6">
        <RemediationSection
          action={
            <Link href="/pr-bundles" className="text-sm text-accent hover:underline">
              View bundle history
            </Link>
          }
          description="Review the grouped execution plan before generating PR bundles for your own pipeline or manual apply workflow."
          eyebrow="Bundle plan"
          title="Review the remediation bundle summary"
          tone="info"
        >
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,0.7fr)]">
            <div className={remediationInsetClass('default')}>
              <p className="text-sm leading-7 text-text/74">
                This screen keeps the current preflight and generation behavior, but reorganizes the work into the same
                dashboard-style hierarchy used in action detail and remediation flows.
              </p>
            </div>
            <div className={remediationInsetClass('default')}>
              <p className="text-xs uppercase tracking-[0.18em] text-muted/70">Selection</p>
              <p className="mt-2 text-sm text-text/78">
                {selectedActions.length > 1
                  ? `${selectedActions.length} actions will be converged into ${executionGroups.length} execution groups.`
                  : 'Single-action bundle generation will use one preflighted strategy.'}
              </p>
            </div>
          </div>
        </RemediationSection>

        {error && <RemediationCallout description={error} title="Unable to build summary" tone="danger" />}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <RemediationStatCard detail="Actions selected for bundle generation." label="Selected actions" value={totals.actionCount} />
          <RemediationStatCard detail="Linked findings represented by the selected actions." label="Covered findings" value={totals.findingCount} />
          <RemediationStatCard detail="Merged account/region/action-type execution groups." label="Execution groups" value={executionGroups.length} />
          <RemediationStatCard detail="Runs created during this session." label="Generated runs" value={generatedRunIds.length} />
        </div>

        <RemediationSection
          description="Use these grouped slices to confirm scope, business context, and account spread before generating bundles."
          eyebrow="Breakdown"
          title="Grouped overview"
        >
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
            <div className={remediationInsetClass('default')}>
              <p className="text-sm font-medium text-text">By account</p>
              <ul className="mt-3 space-y-2 text-sm text-muted">
                {totals.byAccount.map(([key, count]) => (
                  <li key={key} className="font-mono">
                    {key}: {count}
                  </li>
                ))}
              </ul>
            </div>
            <div className={remediationInsetClass('default')}>
              <p className="text-sm font-medium text-text">By matrix cell</p>
              <ul className="mt-3 space-y-2 text-sm text-muted">
                {totals.byMatrix.map(([key, count]) => (
                  <li key={key}>
                    {key}: {count}
                  </li>
                ))}
              </ul>
            </div>
            <div className={remediationInsetClass('default')}>
              <p className="text-sm font-medium text-text">By region</p>
              <ul className="mt-3 space-y-2 text-sm text-muted">
                {totals.byRegion.map(([key, count]) => (
                  <li key={key} className="font-mono">
                    {key}: {count}
                  </li>
                ))}
              </ul>
            </div>
            <div className={remediationInsetClass('default')}>
              <p className="text-sm font-medium text-text">By action type</p>
              <ul className="mt-3 space-y-2 text-sm text-muted">
                {totals.byType.map(([key, count]) => (
                  <li key={key} className="font-mono">
                    {key}: {count}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </RemediationSection>

        <RemediationSection
          description="Execution lanes show how groups are partitioned for concurrent generation while keeping related work together."
          eyebrow="Lane planning"
          title="Parallel lanes"
        >
          <div className="grid gap-4 xl:grid-cols-3">
            {executionLanes.map((lane) => (
              <div key={lane.index} className={remediationInsetClass('default')}>
                <p className="text-sm font-semibold text-text">Lane {lane.index + 1}</p>
                <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted/70">Cost {lane.cost}</p>
                <ul className="mt-4 space-y-2 text-xs text-text">
                  {lane.groups.map((group) => (
                    <li key={group.key} className={remediationInsetClass('default', 'break-all p-3 font-mono')}>
                      {group.action_type} | {group.account_id} | {group.region || 'global'} | {group.status} ({group.actionCount})
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </RemediationSection>

        <RemediationSection
          description="These are the exact actions included in the upcoming bundle generation step."
          eyebrow="Selected actions"
          title="Action list"
        >
          <div className={remediationTableWrapperClass()}>
            <table className="w-full text-sm">
              <thead className="bg-bg/70">
                <tr className="text-left text-muted">
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
                    <td className="px-4 py-6 text-muted" colSpan={6}>
                      Loading summary...
                    </td>
                  </tr>
                )}
                {!isLoading && selectedActions.length === 0 && (
                  <tr>
                    <td className="px-4 py-6 text-muted" colSpan={6}>
                      No selected actions found.
                    </td>
                  </tr>
                )}
                {!isLoading &&
                  selectedActions.map((action) => (
                    <tr key={action.id} className="border-t border-border/45">
                      <td className="px-4 py-3 text-text">{action.title}</td>
                      <td className="px-4 py-3 font-mono text-muted">{action.control_id || '—'}</td>
                      <td className="px-4 py-3 font-mono text-muted">{action.account_id}</td>
                      <td className="px-4 py-3 font-mono text-muted">{action.region || 'global'}</td>
                      <td className="px-4 py-3">
                        <div className="text-text">{formatMatrixLabel(action)}</div>
                        <div className="text-xs text-muted">
                          {titleCaseToken(
                            action.business_impact.criticality.status === 'unknown'
                              ? 'unknown criticality'
                              : action.business_impact.criticality.tier,
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-text">{action.finding_count}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </RemediationSection>

        <div className={remediationInsetClass('default', 'flex flex-wrap items-center gap-2')}>
          <Button variant="secondary" onClick={() => router.push('/pr-bundles/create')}>
            Back to selection
          </Button>
          <Button variant="primary" onClick={handleGenerate} disabled={isGenerating || selectedActions.length === 0}>
            {isGenerating
              ? 'Generating...'
              : selectedActions.length > 1
                ? `Generate ${executionGroups.length} execution bundle${executionGroups.length === 1 ? '' : 's'}`
                : 'Generate 1 PR bundle'}
          </Button>
        </div>

        {result && (
          <RemediationSection
            description={`Generation complete: ${result.succeeded.length} succeeded, ${result.failed.length} failed.`}
            eyebrow="Result"
            title="Bundle generation summary"
            tone={result.failed.length > 0 ? 'warning' : 'success'}
          >
            {result.failed.length > 0 ? (
              <ul className="space-y-2 text-xs text-danger">
                {result.failed.map((item) => (
                  <li key={item.actionId} className={remediationInsetClass('danger', 'break-all p-3 font-mono')}>
                    {item.actionId}: {item.message}
                  </li>
                ))}
              </ul>
            ) : (
              <RemediationCallout
                description="All selected bundle runs were created successfully."
                title="No generation failures"
                tone="success"
              />
            )}
          </RemediationSection>
        )}
      </div>
    </AppShell>
  );
}

export default function PrBundleSummaryPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="PR Bundle Summary">
          <div className={remediationInsetClass('default', 'p-6 text-sm text-muted')}>
            Loading PR bundle summary...
          </div>
        </AppShell>
      }
    >
      <PrBundleSummaryPageContent />
    </Suspense>
  );
}
