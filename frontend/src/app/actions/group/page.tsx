'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { buttonClassName } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { BackgroundJobsProgressBanner } from '@/components/ui/BackgroundJobsProgressBanner';
import { PendingConfirmationNote } from '@/components/ui/PendingConfirmationNote';
import { RemediationStateBadge } from '@/components/ui/RemediationStateBadge';
import { TenantIdForm } from '@/components/TenantIdForm';
import {
  ActionGroupDetail,
  RemediationOption,
  ActionGroupRunResultItem,
  ActionGroupSharedExecutionResultItem,
  ActionGroupRunTimelineItem,
  createActionGroupBundleRun,
  getActionGroup,
  getActionGroups,
  getActionGroupRuns,
  getRemediationOptions,
  getRemediationRun,
  getErrorMessage,
  isApiError,
} from '@/lib/api';
import { downloadPrBundleZip } from '@/lib/pr-bundle-download';
import { useTenantId } from '@/lib/tenant';
import { useAuth } from '@/contexts/AuthContext';
import {
  buildInitialStrategyInputValues,
  buildStrategyInputs,
  deriveAutoPrOnlySelection,
  selectInitialStrategyForMode,
} from '@/lib/remediationAutoSelection';
import {
  hasBlockingChecks,
  requiresRiskAcknowledgement,
  strategyWarningMessages,
} from '@/lib/remediationOptionSupport';
import { getRemediationOutcomePresentation } from '@/lib/remediationOutcome';
import { getRemediationStatePresentation } from '@/lib/remediationState';
import { CONTROL_FAMILY_TOOLTIP, getActionControlSummary } from '@/lib/controlFamily';

export const dynamic = 'force-dynamic';

function bucketLabel(bucket: string): string {
  return getRemediationStatePresentation(bucket, true)?.label || 'Not generated yet';
}

function bucketVariant(bucket: string): 'success' | 'warning' | 'info' | 'default' | 'danger' {
  return getRemediationStatePresentation(bucket, true)?.variant || 'default';
}

function bucketPresentation(bucket: string) {
  return getRemediationStatePresentation(bucket, true);
}

function runStatusVariant(status: string): 'success' | 'warning' | 'info' | 'default' | 'danger' {
  if (status === 'finished' || status === 'success') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'cancelled') return 'warning';
  if (status === 'started' || status === 'running') return 'info';
  return 'default';
}

function formatTime(value: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleString();
}

function outcomeVariant(result: ActionGroupRunResultItem): 'success' | 'warning' | 'info' | 'default' | 'danger' {
  if (result.result_type === 'non_executable') return 'warning';
  return runStatusVariant(result.execution_status);
}

function summarizeOutcomes(results: ActionGroupRunResultItem[]): string {
  const executable = results.filter((result) => result.result_type !== 'non_executable').length;
  const metadataOnly = results.length - executable;
  const failed = results.filter((result) => result.execution_status === 'failed').length;
  const succeeded = results.filter((result) => result.execution_status === 'success').length;
  return `${succeeded} succeeded · ${failed} failed · ${executable} executable · ${metadataOnly} needs review/manual follow-up`;
}

function summarizeSharedExecution(results: ActionGroupSharedExecutionResultItem[]): string {
  const failed = results.filter((result) => result.execution_status === 'failed').length;
  const succeeded = results.filter((result) => result.execution_status === 'success').length;
  return `${succeeded} shared steps succeeded · ${failed} shared steps failed`;
}

function sharedExecutionLabel(kind: string): string {
  if (kind === 's3_access_logging_destination_setup') return 'Shared S3.9 destination setup';
  return kind || 'Shared setup';
}

function supportTierLabel(supportTier: string | null): string {
  const presentation = getRemediationOutcomePresentation(supportTier);
  if (presentation) return presentation.label;
  return supportTier || 'non_executable';
}

function nonExecutableReasonLabel(reason: string | null, supportTier: string | null): string {
  if (reason === 'review_required_metadata_only') {
    return supportTierLabel('review_required_bundle');
  }
  if (reason === 'manual_guidance_metadata_only') {
    return supportTierLabel('manual_guidance_only');
  }
  return supportTierLabel(supportTier);
}

function nonExecutableExplanation(result: ActionGroupRunResultItem): string {
  if (result.decision_rationale) return result.decision_rationale;
  const presentation = getRemediationOutcomePresentation(result.support_tier);
  if (presentation) return presentation.description;
  return 'The platform could not determine a truthful automatic change for this action.';
}

function nonExecutableDestinationBucket(result: ActionGroupRunResultItem): string | null {
  const preserved = result.preservation_summary?.destination_bucket_name;
  if (typeof preserved === 'string' && preserved.trim()) return preserved.trim();
  const strategyValue = result.strategy_inputs?.log_bucket_name;
  if (typeof strategyValue === 'string' && strategyValue.trim()) return strategyValue.trim();
  return null;
}

function extractRiskAcknowledgementFeedback(error: unknown): { message: string; warnings: string[] } | null {
  if (!isApiError(error) || typeof error.detail !== 'object' || error.detail === null) return null;
  const detail = error.detail as Record<string, unknown>;
  if (detail.error !== 'Risk acknowledgement required') return null;
  const message =
    typeof detail.detail === 'string' && detail.detail
      ? detail.detail
      : 'Review dependency warnings and acknowledge risk before continuing.';
  const riskSnapshot =
    typeof detail.risk_snapshot === 'object' && detail.risk_snapshot !== null
      ? (detail.risk_snapshot as Record<string, unknown>)
      : null;
  const warningMessages = new Set<string>();
  const checks = Array.isArray(riskSnapshot?.checks) ? riskSnapshot.checks : [];
  for (const check of checks) {
    if (!check || typeof check !== 'object') continue;
    const status = typeof (check as { status?: unknown }).status === 'string'
      ? String((check as { status?: unknown }).status)
      : '';
    const checkMessage = typeof (check as { message?: unknown }).message === 'string'
      ? String((check as { message?: unknown }).message).trim()
      : '';
    if ((status === 'warn' || status === 'unknown') && checkMessage) {
      warningMessages.add(checkMessage);
    }
  }
  const warnings = Array.isArray(riskSnapshot?.warnings) ? riskSnapshot.warnings : [];
  for (const warning of warnings) {
    if (typeof warning === 'string' && warning.trim()) {
      warningMessages.add(warning.trim());
    }
  }
  if (warningMessages.size === 0) {
    warningMessages.add(message);
  }
  return { message, warnings: [...warningMessages] };
}

function outcomeHeadline(result: ActionGroupRunResultItem): string {
  if (result.result_type === 'non_executable') {
    return nonExecutableReasonLabel(result.reason, result.support_tier);
  }
  return result.execution_status;
}

function sortResultsByMemberOrder(
  results: ActionGroupRunResultItem[],
  memberOrderByActionId: Map<string, number>
): ActionGroupRunResultItem[] {
  return [...results].sort((left, right) => {
    const leftIndex = memberOrderByActionId.get(left.action_id) ?? Number.MAX_SAFE_INTEGER;
    const rightIndex = memberOrderByActionId.get(right.action_id) ?? Number.MAX_SAFE_INTEGER;
    if (leftIndex !== rightIndex) {
      return leftIndex - rightIndex;
    }
    return left.action_id.localeCompare(right.action_id);
  });
}

async function resolveGroupBundleRequest(
  group: ActionGroupDetail,
  tenantId?: string,
): Promise<{
  body: { strategy_id?: string; strategy_inputs?: Record<string, unknown> };
  warnings: string[];
  requiresRiskAck: boolean;
  hasBlockingChecks: boolean;
}> {
  const actionId = group.members[0]?.action_id;
  if (!actionId) return { body: {}, warnings: [], requiresRiskAck: false, hasBlockingChecks: false };
  const options = await getRemediationOptions(actionId, tenantId);
  const autoSelection = deriveAutoPrOnlySelection(options, group.account_id, group.region);
  const selectedStrategy =
    autoSelection.strategy ?? selectInitialStrategyForMode(options.strategies, 'pr_only');
  if (autoSelection.ok) {
    return {
      body: autoSelection.strategyId
        ? { strategy_id: autoSelection.strategyId, strategy_inputs: autoSelection.strategyInputs }
        : {},
      warnings: strategyWarningMessages(selectedStrategy),
      requiresRiskAck: requiresRiskAcknowledgement(selectedStrategy),
      hasBlockingChecks: hasBlockingChecks(selectedStrategy),
    };
  }
  const fallbackStrategy = selectedStrategy;
  if (!fallbackStrategy) throw new Error(autoSelection.message);
  return {
    body: {
      strategy_id: fallbackStrategy.strategy_id,
      strategy_inputs: buildStrategyInputs(fallbackStrategy, buildInitialStrategyInputValues(fallbackStrategy)),
    },
    warnings: strategyWarningMessages(fallbackStrategy),
    requiresRiskAck: requiresRiskAcknowledgement(fallbackStrategy),
    hasBlockingChecks: hasBlockingChecks(fallbackStrategy),
  };
}

type ResolvedGroupBundleRequest = Awaited<ReturnType<typeof resolveGroupBundleRequest>>;

function ActionGroupDetailPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { tenantId, setTenantId } = useTenantId();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const effectiveTenantId = isAuthenticated ? undefined : tenantId;
  const showContent = isAuthenticated || tenantId;

  const legacyActionType = (searchParams.get('action_type') || '').trim();
  const legacyAccountId = (searchParams.get('account_id') || '').trim();
  const legacyRegion = (searchParams.get('region') || '').trim();
  const initialGroupId = (searchParams.get('group_id') || '').trim();

  const [groupId, setGroupId] = useState<string>(initialGroupId);
  const [group, setGroup] = useState<ActionGroupDetail | null>(null);
  const [runs, setRuns] = useState<ActionGroupRunTimelineItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [downloadingRunId, setDownloadingRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedRunIds, setExpandedRunIds] = useState<string[]>([]);
  const [riskAcknowledged, setRiskAcknowledged] = useState(false);
  const [requiresRiskAcknowledgement, setRequiresRiskAcknowledgement] = useState(false);
  const [riskWarnings, setRiskWarnings] = useState<string[]>([]);
  const [pendingBundleSelection, setPendingBundleSelection] = useState<ResolvedGroupBundleRequest | null>(null);

  const resolveLegacyGroup = useCallback(async () => {
    if (initialGroupId || !legacyActionType || !legacyAccountId) {
      if (initialGroupId) setGroupId(initialGroupId);
      return;
    }
    const page = await getActionGroups(
      {
        action_type: legacyActionType,
        account_id: legacyAccountId,
        region: legacyRegion || undefined,
        limit: 1,
        offset: 0,
      },
      effectiveTenantId
    );
    const resolved = page.items[0];
    if (!resolved) {
      throw new Error('No persistent action group found for the provided legacy query parameters.');
    }
    setGroupId(resolved.id);
    const next = new URLSearchParams(searchParams.toString());
    next.set('group_id', resolved.id);
    router.replace(`/actions/group?${next.toString()}`);
  }, [
    effectiveTenantId,
    initialGroupId,
    legacyActionType,
    legacyAccountId,
    legacyRegion,
    router,
    searchParams,
  ]);

  const fetchGroup = useCallback(async () => {
    if (!showContent) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      await resolveLegacyGroup();
      const resolvedGroupId = (searchParams.get('group_id') || groupId || '').trim();
      if (!resolvedGroupId) {
        throw new Error('Missing group_id. Open this page from the persistent Actions group list.');
      }
      const [detail, timeline] = await Promise.all([
        getActionGroup(resolvedGroupId, effectiveTenantId),
        getActionGroupRuns(resolvedGroupId, { limit: 100, offset: 0 }, effectiveTenantId),
      ]);
      setGroupId(resolvedGroupId);
      setGroup(detail);
      setRuns(timeline.items);
    } catch (err) {
      setError(getErrorMessage(err));
      setGroup(null);
      setRuns([]);
    } finally {
      setIsLoading(false);
    }
  }, [showContent, resolveLegacyGroup, searchParams, groupId, effectiveTenantId]);

  useEffect(() => {
    void fetchGroup();
  }, [fetchGroup]);

  useEffect(() => {
    if (runs.length === 0) {
      setExpandedRunIds([]);
      return;
    }
    setExpandedRunIds([runs[0].id]);
  }, [runs]);

  useEffect(() => {
    setRiskAcknowledged(false);
    setRequiresRiskAcknowledgement(false);
    setRiskWarnings([]);
    setPendingBundleSelection(null);
  }, [groupId]);

  const handleGenerateBundle = useCallback(async () => {
    if (!groupId || !group) return;
    setIsGenerating(true);
    setError(null);
    let selection = pendingBundleSelection;
    try {
      if (!selection) {
        selection = await resolveGroupBundleRequest(group, effectiveTenantId);
        setPendingBundleSelection(selection);
      }
      const acknowledgementRequired = selection.requiresRiskAck || requiresRiskAcknowledgement;
      setRequiresRiskAcknowledgement(acknowledgementRequired);
      setRiskWarnings(selection.warnings);
      if (selection.hasBlockingChecks) {
        setError('Safety gate blocked this remediation strategy. Resolve failing dependency checks first.');
        return;
      }
      if (acknowledgementRequired && !riskAcknowledged) {
        setError('Review dependency warnings and acknowledge risk before continuing.');
        return;
      }
      await createActionGroupBundleRun(
        groupId,
        {
          ...selection.body,
          ...(acknowledgementRequired && riskAcknowledged ? { risk_acknowledged: true } : {}),
        },
        effectiveTenantId
      );
      setPendingBundleSelection(null);
      setRequiresRiskAcknowledgement(false);
      await fetchGroup();
    } catch (err) {
      const riskAckFeedback = extractRiskAcknowledgementFeedback(err);
      if (riskAckFeedback) {
        setRequiresRiskAcknowledgement(true);
        setRiskWarnings(riskAckFeedback.warnings);
        if (selection) {
          setPendingBundleSelection({
            ...selection,
            requiresRiskAck: true,
            warnings: riskAckFeedback.warnings,
          });
        }
        setError(riskAckFeedback.message);
        return;
      }
      setError(getErrorMessage(err));
    } finally {
      setIsGenerating(false);
    }
  }, [
    groupId,
    group,
    effectiveTenantId,
    fetchGroup,
    pendingBundleSelection,
    requiresRiskAcknowledgement,
    riskAcknowledged,
  ]);

  const handleDownload = useCallback(async (run: ActionGroupRunTimelineItem) => {
    if (!run.remediation_run_id) return;
    setDownloadingRunId(run.id);
    setError(null);
    try {
      const remediationRun = await getRemediationRun(run.remediation_run_id, effectiveTenantId);
      const files = (
        remediationRun.artifacts as { pr_bundle?: { files?: { path: string; content: string }[] } } | null
      )?.pr_bundle?.files;
      if (!files?.length) {
        throw new Error('No PR bundle files are available for this run.');
      }
      await downloadPrBundleZip(run.remediation_run_id, files);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setDownloadingRunId(null);
    }
  }, [effectiveTenantId]);

  const counterCards = useMemo(() => {
    if (!group) return [];
    return [
      { label: 'Generated and successful', value: group.counters.run_successful },
      { label: 'Metadata-only', value: group.counters.metadata_only },
      { label: 'Total actions', value: group.counters.total_actions },
    ];
  }, [group]);

  const membersByActionId = useMemo(() => {
    return new Map(group?.members.map((member) => [member.action_id, member]) ?? []);
  }, [group]);

  const memberOrderByActionId = useMemo(() => {
    return new Map(group?.members.map((member, index) => [member.action_id, index]) ?? []);
  }, [group]);

  const pendingConfirmationSummary = useMemo(() => {
    if (!group) return null;
    const notedMembers = group.members.filter(
      (member) => member.status_message && member.status_severity
    );
    if (notedMembers.length === 0) return null;
    const warningMember = notedMembers.find((member) => member.status_severity === 'warning');
    const representative = warningMember || notedMembers[0];
    if (!representative.status_message || !representative.status_severity) {
      return null;
    }
    return {
      count: notedMembers.length,
      message: representative.status_message,
      severity: representative.status_severity,
      followupKind: representative.followup_kind,
    };
  }, [group]);

  const followupMembers = useMemo(() => {
    return group?.members.filter((member) => member.status_bucket === 'run_successful_needs_followup') ?? [];
  }, [group]);

  const toggleRunExpanded = useCallback((runId: string) => {
    setExpandedRunIds((current) =>
      current.includes(runId) ? current.filter((id) => id !== runId) : [...current, runId]
    );
  }, []);

  return (
    <AppShell title="Action Group">
      <div className="max-w-6xl mx-auto w-full">
        {!showContent && !authLoading && isAuthenticated && <TenantIdForm onSave={setTenantId} />}

        {showContent && (
          <>
            <BackgroundJobsProgressBanner types={['actions']} />

            <Link
              href="/findings"
              className="mb-6 inline-flex items-center gap-2 text-muted transition-colors hover:text-text"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
              Back to Findings
            </Link>

            {error && (
              <div className="mb-6 rounded-2xl nm-neu-flat border border-danger/30 bg-danger/10 p-4 text-sm text-danger">
                {error}
              </div>
            )}

            {isLoading && (
              <div className="rounded-2xl nm-neu-lg border-none p-6 text-sm text-muted">
                Loading persistent group details...
              </div>
            )}

            {!isLoading && group && (
              <div className="space-y-6">
                <section className="rounded-[2rem] nm-neu-lg border-none p-8">
                  <div className="flex flex-wrap items-start justify-between gap-6">
                    <div>
                      <h1 className="text-2xl font-bold text-text">{group.action_type}</h1>
                      <p className="mt-2 text-sm text-muted font-medium">
                        Account <span className="text-text">{group.account_id}</span>
                        {group.region ? ` · ${group.region}` : ' · global'}
                      </p>
                      <p className="mt-2 text-xs text-muted font-mono bg-bg px-2 py-1 rounded-lg inline-block">
                        Group ID: {group.id}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                      <Link href="/pr-bundles">
                        <Button variant="secondary">
                          View PR Bundle history →
                        </Button>
                      </Link>
                      <Button
                        onClick={handleGenerateBundle}
                        disabled={isGenerating || !group.can_generate_bundle || (requiresRiskAcknowledgement && !riskAcknowledged)}
                      >
                        {isGenerating ? 'Generating…' : 'Generate bundle'}
                      </Button>
                    </div>
                  </div>
                  {!group.can_generate_bundle && group.blocked_detail && (
                    <div className="mt-4 rounded-2xl nm-neu-flat border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
                      {group.blocked_detail}
                    </div>
                  )}
                  {requiresRiskAcknowledgement && (
                    <div className="mt-4 rounded-2xl nm-neu-flat border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
                      <p className="font-semibold text-text">Review required before generating this bundle.</p>
                      <div className="mt-2 space-y-2">
                        {riskWarnings.map((warning, index) => (
                          <p key={`${warning}-${index}`}>{warning}</p>
                        ))}
                      </div>
                      <label className="mt-4 flex items-start gap-3 text-sm text-text">
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4 rounded border-border"
                          checked={riskAcknowledged}
                          onChange={(event) => setRiskAcknowledged(event.target.checked)}
                        />
                        <span>I reviewed the dependency warnings for this strategy and want to continue.</span>
                      </label>
                    </div>
                  )}

                  <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
                    {counterCards.map((card) => (
                      <div key={card.label} className="rounded-2xl nm-neu-sm border-none p-5">
                        <p className="text-xs font-bold uppercase tracking-wider text-muted opacity-70">{card.label}</p>
                        <p className="mt-2 text-3xl font-bold text-text tracking-tight">{card.value}</p>
                      </div>
                    ))}
                  </div>
                  {pendingConfirmationSummary && (
                    <div className="mt-6 space-y-2">
                      <p className="text-xs font-bold uppercase tracking-wider text-muted opacity-70">
                        {pendingConfirmationSummary.followupKind === 'awaiting_aws_confirmation'
                          ? `Pending source-of-truth confirmation · ${pendingConfirmationSummary.count}`
                          : `Post-generation follow-up · ${pendingConfirmationSummary.count}`}
                      </p>
                      <PendingConfirmationNote
                        message={pendingConfirmationSummary.message}
                        severity={pendingConfirmationSummary.severity}
                      />
                    </div>
                  )}
                </section>

                <section className="rounded-[2rem] nm-neu-lg border-none p-8">
                  <h2 className="mb-6 text-lg font-bold uppercase tracking-tight text-text">
                    Generated and needs follow-up
                  </h2>
                  <div className="space-y-4">
                    {followupMembers.length === 0 && (
                      <div className="rounded-2xl nm-neu-pressed border-none p-6 text-sm font-medium italic text-muted">
                        No generated follow-up actions right now.
                      </div>
                    )}
                    {followupMembers.map((member) => (
                      <div
                        key={member.action_id}
                        className="rounded-2xl nm-neu-sm border-none p-5"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-4">
                          <div className="min-w-0">
                            <p className="text-sm font-bold text-text leading-tight">{member.title}</p>
                            <p
                              className="text-xs text-muted font-mono mt-2 bg-bg/50 px-2 py-1 rounded inline-block"
                              title={member.control_family?.is_mapped ? CONTROL_FAMILY_TOOLTIP : undefined}
                            >
                              {getActionControlSummary(member.control_family, member.control_id) || 'n/a'} · {member.resource_id || 'resource n/a'}
                            </p>
                          </div>
                          <div className="flex items-center gap-3">
                            {bucketPresentation(member.status_bucket) ? (
                              <RemediationStateBadge
                                presentation={bucketPresentation(member.status_bucket)!}
                              />
                            ) : (
                              <Badge variant={bucketVariant(member.status_bucket)}>
                                {bucketLabel(member.status_bucket)}
                              </Badge>
                            )}
                            <Badge variant="info" className="nm-neu-flat border-none px-3">P{member.priority}</Badge>
                          </div>
                        </div>
                        <div className="mt-4 grid grid-cols-1 gap-4 text-[11px] font-medium text-muted sm:grid-cols-3">
                          <div className="flex flex-col gap-1">
                            <span className="uppercase opacity-60">Last attempt</span>
                            <span className="text-text">{formatTime(member.last_attempt_at)}</span>
                          </div>
                          <div className="flex flex-col gap-1">
                            <span className="uppercase opacity-60">Last confirmed</span>
                            <span className="text-text">{formatTime(member.last_confirmed_at)}</span>
                          </div>
                          <div className="flex flex-col gap-1">
                            <span className="uppercase opacity-60">Latest generation</span>
                            <span className="text-text">{member.latest_run.status || '—'}</span>
                          </div>
                        </div>
                        {member.status_message &&
                          member.status_severity && (
                            <div className="mt-4">
                              <PendingConfirmationNote
                                message={member.status_message}
                                severity={member.status_severity}
                                compact
                              />
                            </div>
                          )}
                        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl nm-neu-pressed border-none p-4">
                          <p className="text-sm text-muted">
                            Complete the remaining manual fix, then open this action and click <span className="font-semibold text-text">Refresh State</span>.
                          </p>
                          <Link
                            href={`/actions/${encodeURIComponent(member.action_id)}`}
                            className={buttonClassName({ variant: 'secondary', size: 'sm' })}
                          >
                            Open action and refresh state
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="rounded-[2rem] nm-neu-lg border-none p-8">
                  <h2 className="text-lg font-bold text-text uppercase tracking-tight mb-6">Generation timeline</h2>
                  <div className="space-y-4">
                    {runs.length === 0 && (
                      <div className="rounded-2xl nm-neu-pressed border-none p-6 text-sm font-medium text-muted text-center italic">
                        No generations yet.
                      </div>
                    )}
                    {runs.map((run) => {
                      const orderedResults = sortResultsByMemberOrder(run.results, memberOrderByActionId);
                      const isExpanded = expandedRunIds.includes(run.id);
                      return (
                        <div key={run.id} className="rounded-2xl nm-neu-sm border-none p-5">
                          <div className="flex flex-wrap items-center justify-between gap-4">
                            <div className="space-y-1">
                              <p className="text-sm font-bold text-text leading-tight">Generation {run.id}</p>
                              <p className="text-xs text-muted font-medium">
                                {run.mode} · started {formatTime(run.started_at)} · finished {formatTime(run.finished_at)}
                              </p>
                            </div>
                            <div className="flex flex-wrap items-center gap-3">
                              {orderedResults.length > 0 && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => toggleRunExpanded(run.id)}
                                >
                                  {isExpanded ? 'Hide outcomes' : 'Show outcomes'}
                                </Button>
                              )}
                              <Badge variant={runStatusVariant(run.status)}>{run.status}</Badge>
                              {run.remediation_run_id && (
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => void handleDownload(run)}
                                  disabled={downloadingRunId === run.id}
                                >
                                  {downloadingRunId === run.id ? 'Downloading…' : 'Download Bundle'}
                                </Button>
                              )}
                            </div>
                          </div>
                          {orderedResults.length > 0 && (
                            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl nm-neu-pressed border-none px-4 py-3">
                              <p className="text-xs font-bold uppercase tracking-wider text-muted opacity-70">
                                Per-action outcomes
                              </p>
                              <p className="text-[11px] font-medium text-muted">{summarizeOutcomes(orderedResults)}</p>
                            </div>
                          )}
                          {run.shared_execution_results.length > 0 && (
                            <div className="mt-4 rounded-2xl nm-neu-pressed border-none px-4 py-3">
                              <div className="flex flex-wrap items-center justify-between gap-3">
                                <p className="text-xs font-bold uppercase tracking-wider text-muted opacity-70">
                                  Shared setup diagnostics
                                </p>
                                <p className="text-[11px] font-medium text-muted">
                                  {summarizeSharedExecution(run.shared_execution_results)}
                                </p>
                              </div>
                              <div className="mt-3 space-y-3">
                                {run.shared_execution_results.map((result) => (
                                  <div key={result.folder} className="rounded-xl nm-neu-flat border-none p-4">
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                      <div className="min-w-0">
                                        <p className="text-sm font-bold text-text leading-tight">
                                          {sharedExecutionLabel(result.kind)}
                                        </p>
                                        <p className="mt-2 text-xs text-muted font-mono bg-bg/50 px-2 py-1 rounded inline-block">
                                          {result.folder}
                                        </p>
                                      </div>
                                      <Badge variant={runStatusVariant(result.execution_status)}>
                                        {result.execution_status}
                                      </Badge>
                                    </div>
                                    <div className="mt-3 space-y-1 text-xs font-medium text-muted">
                                      {typeof result.details.destination_bucket_name === 'string' && result.details.destination_bucket_name && (
                                        <p>
                                          Destination bucket:{' '}
                                          <span className="text-text">{result.details.destination_bucket_name}</span>
                                        </p>
                                      )}
                                      {result.execution_error_message && (
                                        <p className="text-danger">
                                          Error: <span className="text-danger/90">{result.execution_error_message}</span>
                                        </p>
                                      )}
                                      {result.execution_error_code && (
                                        <p>
                                          Code: <span className="text-text">{result.execution_error_code}</span>
                                        </p>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {orderedResults.length > 0 && isExpanded && (
                            <div className="mt-4 rounded-2xl nm-neu-pressed border-none p-4">
                              <div className="flex flex-wrap items-center justify-between gap-3">
                                <p className="text-xs font-bold uppercase tracking-wider text-muted opacity-70">
                                  Per-action outcomes
                                </p>
                                <p className="text-[11px] font-medium text-muted">{summarizeOutcomes(orderedResults)}</p>
                              </div>
                              <div className="mt-4 space-y-3">
                                {orderedResults.map((result) => {
                                  const member = membersByActionId.get(result.action_id);
                                  return (
                                    <div key={result.action_id} className="rounded-xl nm-neu-flat border-none p-4">
                                      <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div className="min-w-0">
                                          <p className="text-sm font-bold text-text leading-tight">
                                            {member?.title || `Action ${result.action_id}`}
                                          </p>
                                          <p className="mt-2 text-xs text-muted font-mono bg-bg/50 px-2 py-1 rounded inline-block">
                                            {(getActionControlSummary(member?.control_family, member?.control_id) || 'n/a')} · {result.action_id}
                                          </p>
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                          <Badge variant={outcomeVariant(result)}>{outcomeHeadline(result)}</Badge>
                                          {result.result_type === 'non_executable' && result.support_tier && (
                                            <Badge variant="warning">{supportTierLabel(result.support_tier)}</Badge>
                                          )}
                                        </div>
                                      </div>
                                      <div className="mt-3 space-y-1 text-xs font-medium text-muted">
                                        {result.result_type === 'non_executable' && (
                                          <p className="text-text">
                                            Why no automatic actions were included:{' '}
                                            <span className="text-muted">{nonExecutableExplanation(result)}</span>
                                          </p>
                                        )}
                                        {result.result_type === 'non_executable' && nonExecutableDestinationBucket(result) && (
                                          <p>
                                            Destination bucket:{' '}
                                            <span className="text-text">{nonExecutableDestinationBucket(result)}</span>
                                          </p>
                                        )}
                                        {result.execution_error_message && (
                                          <p className="text-danger">
                                            Error: <span className="text-danger/90">{result.execution_error_message}</span>
                                          </p>
                                        )}
                                        {result.blocked_reasons.length > 0 && (
                                          <p>
                                            Blocked by:{' '}
                                            <span className="text-text">{result.blocked_reasons.join(' · ')}</span>
                                          </p>
                                        )}
                                        <p>
                                          Started {formatTime(result.execution_started_at)} · Finished{' '}
                                          {formatTime(result.execution_finished_at)}
                                        </p>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}

export default function ActionGroupDetailPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="Action Group">
          <div className="max-w-6xl mx-auto w-full rounded-xl border border-border bg-surface p-6 text-sm text-muted">
            Loading action group details...
          </div>
        </AppShell>
      }
    >
      <ActionGroupDetailPageContent />
    </Suspense>
  );
}
