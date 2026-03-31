'use client';

import { Suspense, useEffect, useRef, useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'motion/react';
import { useSearchParams } from 'next/navigation';
import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { SelectDropdown } from '@/components/ui/SelectDropdown';
import { PlaceholdersAndVanishInput } from '@/components/ui/placeholders-and-vanish-input';
import { BackgroundJobsProgressBanner } from '@/components/ui/BackgroundJobsProgressBanner';
import { TenantIdForm } from '@/components/TenantIdForm';
import {
  getFindings,
  getActions,
  getAccounts,
  triggerComputeActions,
  triggerIngest,
  getFindingGroups,
  Finding,
  FindingGroup,
  FindingGroupActionResponse,
  AwsAccount,
  FindingsFilters,
  FindingGroupsFilters,
  getScopeMeta,
  ScopeMetaResponse,
  getErrorMessage,
} from '@/lib/api';
import { useTenantId } from '@/lib/tenant';
import { useAuth } from '@/contexts/AuthContext';
import { useBackgroundJobs } from '@/contexts/BackgroundJobsContext';
import { FindingCard } from './FindingCard';
import { FindingGroupCard } from './FindingGroupCard';
import { GroupingControlBar, GroupingDimension } from './GroupingControlBar';
import { GroupedFindingsView } from './GroupedFindingsView';
import { SeverityTabs } from './SeverityTabs';
import { Pagination } from './Pagination';
import { getSourceLabel, SOURCE_FILTER_VALUES } from '@/lib/source';
import { ActionDetailModal } from '@/components/ActionDetailModal';
import { logError } from '@/lib/errorLogger';
import {
  classifyFindingGroupRemediationFocus,
  classifyFindingRemediationFocus,
  getRemediationFocusPresentation,
  REMEDIATION_FOCUS_ORDER,
  type RemediationFocusBucket,
} from '@/lib/remediationFocus';

export const dynamic = 'force-dynamic';

const LIMIT = 20;
const FIRST_RUN_STORAGE_KEY = 'first_login_processing_v1';
const FIRST_RUN_SOFT_TIMEOUT_MS = 120 * 1000;
const FIRST_RUN_HARD_TIMEOUT_MS = 15 * 60 * 1000;
const DEFAULT_OPEN_FINDINGS_STATUS = 'NEW,NOTIFIED';
const REMEDIATION_FILTER_OPTIONS = REMEDIATION_FOCUS_ORDER.filter(
  (bucket) => bucket !== 'resolved_or_other'
);

function normalizeQueryValue(value: string | null): string | null {
  const trimmed = (value || '').trim();
  return trimmed.length > 0 ? trimmed : null;
}

function normalizeCsvQueryValue(value: string | null, uppercase: boolean): string | null {
  if (!value) return null;
  const items = value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => (uppercase ? item.toUpperCase() : item));
  return items.length > 0 ? items.join(',') : null;
}

function getStatusFilterLabel(value: string): string {
  return value === DEFAULT_OPEN_FINDINGS_STATUS ? 'Open' : value;
}

function FindingsPageContent() {
  const searchParams = useSearchParams();
  const requestedViewMode = searchParams.get('view');
  const { tenantId, setTenantId } = useTenantId();
  const { isAuthenticated, user } = useAuth();
  const { jobs, addJob, updateJob, completeJob, timeoutJob, failJob } = useBackgroundJobs();

  // Data state
  const [findings, setFindings] = useState<Finding[]>([]);
  const [total, setTotal] = useState(0);
  const [accounts, setAccounts] = useState<AwsAccount[]>([]);
  const [scopeMeta, setScopeMeta] = useState<ScopeMetaResponse | null>(null);

  // Grouped view state (Phase B)
  const [viewMode, setViewMode] = useState<'grouped' | 'flat'>('grouped');
  const [groups, setGroups] = useState<FindingGroup[]>([]);
  const [groupsTotal, setGroupsTotal] = useState(0);
  const [isGroupsLoading, setIsGroupsLoading] = useState(false);
  const [groupsError, setGroupsError] = useState<string | null>(null);
  const [groupsOffset, setGroupsOffset] = useState(0);

  // C4: Default grouping: Severity → Rule
  const [groupingDimensions, setGroupingDimensions] = useState<GroupingDimension[]>(['severity', 'rule']);

  // Filter state
  const [severity, setSeverity] = useState<string | null>(null);
  const [source, setSource] = useState<string>('');
  const [accountId, setAccountId] = useState<string>('');
  const [region, setRegion] = useState<string>('');
  const [controlId, setControlId] = useState<string>('');
  const [resourceId, setResourceId] = useState<string>('');
  const [status, setStatus] = useState<string>(DEFAULT_OPEN_FINDINGS_STATUS);
  const [searchQuery, setSearchQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [remediationFocus, setRemediationFocus] = useState<RemediationFocusBucket | ''>('');

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scopeMetaError, setScopeMetaError] = useState<string | null>(null);
  const [accountsError, setAccountsError] = useState<string | null>(null);
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const [groupActionNotice, setGroupActionNotice] = useState<{ tone: 'success' | 'error'; message: string } | null>(null);

  // First-login processing experience state
  const [firstRunEnabled, setFirstRunEnabled] = useState(false);
  const [firstRunAccountId, setFirstRunAccountId] = useState<string | null>(null);
  const [firstRunStartedAt, setFirstRunStartedAt] = useState<number | null>(null);
  const [firstRunFindingsReady, setFirstRunFindingsReady] = useState(false);
  const [firstRunActionsReady, setFirstRunActionsReady] = useState(false);
  const [firstRunSoftTimeout, setFirstRunSoftTimeout] = useState(false);
  const [firstRunHardTimeout, setFirstRunHardTimeout] = useState(false);
  const [firstRunNotifyWhenReady, setFirstRunNotifyWhenReady] = useState(false);
  const [firstRunFindingsJobId, setFirstRunFindingsJobId] = useState<string | null>(null);
  const [firstRunActionsJobId, setFirstRunActionsJobId] = useState<string | null>(null);
  const findingsRequestIdRef = useRef(0);
  const groupsRequestIdRef = useRef(0);

  const effectiveTenantId = isAuthenticated ? undefined : tenantId;
  const showContent = isAuthenticated || tenantId;

  const onlyInScope = !!scopeMeta?.only_in_scope_controls;
  const disabledSources = useMemo(() => new Set(scopeMeta?.disabled_sources ?? []), [scopeMeta?.disabled_sources]);
  const sourceOptions = useMemo(() => {
    return SOURCE_FILTER_VALUES.map((opt) => ({
      ...opt,
      disabled: onlyInScope && opt.value !== '' && disabledSources.has(opt.value),
    }));
  }, [onlyInScope, disabledSources]);

  // Resolve first-login processing context from query params or persisted onboarding handoff.
  useEffect(() => {
    if (!showContent) return;

    const queryFirstRun = searchParams.get('first_run') === '1';
    const queryAccountId = searchParams.get('account_id');
    const queryFindingsJobId = searchParams.get('findings_job_id');
    const queryActionsJobId = searchParams.get('actions_job_id');

    let accountId = queryAccountId;
    let startedAt: number | null = Date.now();
    let findingsJobId = queryFindingsJobId;
    let actionsJobId = queryActionsJobId;
    let enabled = queryFirstRun;

    if (!enabled && typeof window !== 'undefined') {
      try {
        const raw = localStorage.getItem(FIRST_RUN_STORAGE_KEY);
        if (raw) {
          const stored = JSON.parse(raw) as {
            accountId?: string;
            startedAt?: number;
            findingsJobId?: string;
            actionsJobId?: string;
          };
          if (stored.accountId) {
            enabled = true;
            accountId = stored.accountId;
            startedAt = stored.startedAt ?? Date.now();
            findingsJobId = stored.findingsJobId ?? null;
            actionsJobId = stored.actionsJobId ?? null;
          }
        }
      } catch {
        // ignore malformed local storage state
      }
    }

    if (!enabled || !accountId) return;

    setFirstRunEnabled(true);
    setFirstRunAccountId(accountId);
    setFirstRunStartedAt(startedAt);

    const findingsId =
      findingsJobId ||
      addJob({
        type: 'findings',
        title: 'Loading findings',
        message: `Ingestion in progress for account ${accountId}.`,
        progress: 25,
        resourceId: accountId,
        actorId: user?.id ?? 'anonymous',
        dedupeKey: `first-run-findings:${accountId}:${user?.id ?? 'anonymous'}`,
      });
    const actionsId =
      actionsJobId ||
      addJob({
        type: 'actions',
        title: 'Computing actions',
        message: `Action computation in progress for account ${accountId}.`,
        progress: 25,
        resourceId: accountId,
        actorId: user?.id ?? 'anonymous',
        dedupeKey: `first-run-actions:${accountId}:${user?.id ?? 'anonymous'}`,
      });

    setFirstRunFindingsJobId(findingsId);
    setFirstRunActionsJobId(actionsId);
  }, [addJob, searchParams, showContent, user?.id]);

  // Hydrate filters from URL params so deep links from Top Risks apply immediately.
  useEffect(() => {
    if (!showContent) return;

    if (requestedViewMode === 'flat' || requestedViewMode === 'grouped') {
      setViewMode(requestedViewMode);
    }

    setSeverity(normalizeCsvQueryValue(searchParams.get('severity'), true));
    setStatus(normalizeCsvQueryValue(searchParams.get('status'), true) ?? DEFAULT_OPEN_FINDINGS_STATUS);
    setSource(normalizeCsvQueryValue(searchParams.get('source'), false) ?? '');
    setAccountId(normalizeQueryValue(searchParams.get('account_id')) ?? '');
    setRegion(normalizeQueryValue(searchParams.get('region')) ?? '');
    setControlId(normalizeQueryValue(searchParams.get('control_id')) ?? '');
    setResourceId(normalizeQueryValue(searchParams.get('resource_id')) ?? '');
    setOffset(0);
    setGroupsOffset(0);
  }, [requestedViewMode, searchParams, showContent]);

  // Fetch backend UI meta once (scope + disabled sources).
  useEffect(() => {
    getScopeMeta()
      .then((meta) => {
        setScopeMeta(meta);
        setScopeMetaError(null);
      })
      .catch((err) => {
        const errorToLog = err instanceof Error ? err : new Error('Failed to load scope metadata');
        logError(errorToLog, {
          file: 'frontend/src/app/findings/page.tsx',
          operation: 'getScopeMeta',
        });
        setScopeMetaError('Unable to load scope metadata. Source filtering may be incomplete.');
      });
  }, []);

  // If a disabled source is selected, reset to "All sources" so the UI stays coherent.
  useEffect(() => {
    if (!onlyInScope) return;
    if (!source) return;
    if (disabledSources.has(source)) setSource('');
  }, [onlyInScope, disabledSources, source]);

  // Fetch accounts for dropdown
  useEffect(() => {
    if (!showContent) return;
    getAccounts(effectiveTenantId)
      .then((items) => {
        setAccounts(items);
        setAccountsError(null);
      })
      .catch((err) => {
        const errorToLog = err instanceof Error ? err : new Error('Failed to load account filters');
        logError(errorToLog, {
          file: 'frontend/src/app/findings/page.tsx',
          operation: 'getAccounts',
          tenantId: effectiveTenantId ?? 'auth-session',
        });
        setAccountsError('Unable to load account filters. Account dropdown options may be incomplete.');
      });
  }, [showContent, effectiveTenantId]);

  // Fetch findings
  const fetchFindings = useCallback(async () => {
    if (!showContent) {
      setIsLoading(false);
      return;
    }

    const requestId = ++findingsRequestIdRef.current;
    setIsLoading(true);
    setError(null);

    try {
      const filters: FindingsFilters = {
        limit: LIMIT,
        offset,
      };

      if (severity) filters.severity = severity;
      if (source) filters.source = source;
      if (accountId) filters.account_id = accountId;
      if (region) filters.region = region;
      if (controlId.trim()) filters.control_id = controlId.trim();
      if (resourceId.trim()) filters.resource_id = resourceId.trim();
      if (status) filters.status = status;

      const response = await getFindings(filters, effectiveTenantId);
      if (requestId !== findingsRequestIdRef.current) return;
      setFindings(response.items);
      setTotal(response.total);
    } catch (err) {
      if (requestId !== findingsRequestIdRef.current) return;
      setError(getErrorMessage(err));
    } finally {
      if (requestId !== findingsRequestIdRef.current) return;
      setIsLoading(false);
    }
  }, [showContent, severity, source, accountId, region, controlId, resourceId, status, offset, effectiveTenantId]);

  useEffect(() => {
    fetchFindings();
  }, [fetchFindings]);

  // Grouped view fetch (Phase B)
  const fetchGroups = useCallback(async () => {
    if (!showContent) return;
    const requestId = ++groupsRequestIdRef.current;
    setIsGroupsLoading(true);
    setGroupsError(null);
    try {
      const filters: FindingGroupsFilters = {
        limit: LIMIT,
        offset: groupsOffset,
      };
      if (severity) filters.severity = severity;
      if (source) filters.source = source;
      if (accountId) filters.account_id = accountId;
      if (region) filters.region = region;
      if (status) filters.status = status;
      if (controlId.trim()) filters.control_id = controlId.trim();
      if (resourceId.trim()) filters.resource_id = resourceId.trim();
      const response = await getFindingGroups(filters, effectiveTenantId);
      if (requestId !== groupsRequestIdRef.current) return;
      setGroups(response.items);
      setGroupsTotal(response.total);
    } catch (err) {
      if (requestId !== groupsRequestIdRef.current) return;
      setGroupsError(getErrorMessage(err));
    } finally {
      if (requestId !== groupsRequestIdRef.current) return;
      setIsGroupsLoading(false);
    }
  }, [showContent, severity, source, accountId, region, status, controlId, resourceId, groupsOffset, effectiveTenantId]);


  useEffect(() => {
    if (viewMode === 'grouped') fetchGroups();
  }, [fetchGroups, viewMode]);


  // Safety net for stale first-run findings jobs that can remain "running" even when findings are already visible.
  useEffect(() => {
    if (firstRunEnabled) return;
    if (findings.length === 0) return;

    const staleFirstRunFindings = jobs.filter(
      (job) =>
        job.type === 'findings' &&
        (job.status === 'queued' || job.status === 'running' || job.status === 'partial') &&
        typeof job.dedupeKey === 'string' &&
        job.dedupeKey.startsWith('first-run-findings:')
    );

    for (const job of staleFirstRunFindings) {
      completeJob(job.id, 'Findings loaded.');
    }
  }, [completeJob, findings.length, firstRunEnabled, jobs]);

  useEffect(() => {
    if (!firstRunEnabled || !firstRunAccountId || !firstRunStartedAt) return;
    if (!showContent) return;

    let cancelled = false;

    const runPoll = async () => {
      if (cancelled) return;

      const elapsed = Date.now() - firstRunStartedAt;
      const softTimeout = elapsed >= FIRST_RUN_SOFT_TIMEOUT_MS;
      const hardTimeout = elapsed >= FIRST_RUN_HARD_TIMEOUT_MS;

      if (softTimeout && !firstRunSoftTimeout) {
        setFirstRunSoftTimeout(true);
      }

      if (hardTimeout && !firstRunHardTimeout) {
        setFirstRunHardTimeout(true);
        if (firstRunFindingsJobId) {
          timeoutJob(
            firstRunFindingsJobId,
            'Loading findings timed out.',
            'This can happen in large accounts. You can retry from this panel.'
          );
        }
        if (firstRunActionsJobId) {
          timeoutJob(
            firstRunActionsJobId,
            'Computing actions timed out.',
            'Findings may still be available while action computation catches up.'
          );
        }
        return;
      }

      try {
        const [findingsResponse, actionsResponse] = await Promise.all([
          getFindings({ account_id: firstRunAccountId, limit: 1, offset: 0 }, effectiveTenantId),
          getActions({ account_id: firstRunAccountId, group_by: 'batch', limit: 1, offset: 0 }, effectiveTenantId),
        ]);

        if (cancelled) return;

        const findingsReady = findingsResponse.total > 0;
        const actionsReady = actionsResponse.total > 0;

        if (findingsReady && !firstRunFindingsReady && firstRunFindingsJobId) {
          completeJob(firstRunFindingsJobId, 'Findings loaded.', 'You can now review live findings.');
        } else if (!findingsReady && firstRunFindingsJobId) {
          updateJob(firstRunFindingsJobId, {
            status: 'running',
            progress: Math.min(90, 30 + Math.floor((elapsed / FIRST_RUN_HARD_TIMEOUT_MS) * 50)),
            message: 'Loading findings...',
          });
        }

        if (actionsReady && !firstRunActionsReady && firstRunActionsJobId) {
          completeJob(firstRunActionsJobId, 'Actions computed.', 'Recommended fixes are ready.');
        } else if (!actionsReady && firstRunActionsJobId) {
          updateJob(firstRunActionsJobId, {
            status: softTimeout ? 'partial' : 'running',
            progress: Math.min(90, 20 + Math.floor((elapsed / FIRST_RUN_HARD_TIMEOUT_MS) * 55)),
            message: softTimeout ? 'Actions still computing. Showing partial results.' : 'Computing actions...',
          });
        }

        setFirstRunFindingsReady(findingsReady);
        setFirstRunActionsReady(actionsReady);

        if (findingsReady && actionsReady) {
          setFirstRunEnabled(false);
          setFirstRunSoftTimeout(false);
          setFirstRunHardTimeout(false);
          if (typeof window !== 'undefined') {
            localStorage.removeItem(FIRST_RUN_STORAGE_KEY);
          }
          if (firstRunNotifyWhenReady) {
            const notifyJobId = addJob({
              type: 'system',
              title: 'Initial processing complete',
              message: `Findings and actions are ready for account ${firstRunAccountId}.`,
              progress: 90,
              status: 'running',
              severity: 'info',
            });
            completeJob(notifyJobId, 'Initial processing complete.');
          }
        }
      } catch (pollError) {
        if (cancelled) return;
        if (firstRunFindingsJobId) {
          updateJob(firstRunFindingsJobId, {
            status: 'partial',
            message: `Polling issue: ${getErrorMessage(pollError)}. Retrying...`,
          });
        }
      }
    };

    void runPoll();
    const interval = window.setInterval(() => {
      void runPoll();
    }, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [
    addJob,
    completeJob,
    effectiveTenantId,
    firstRunActionsJobId,
    firstRunActionsReady,
    firstRunAccountId,
    firstRunEnabled,
    firstRunFindingsJobId,
    firstRunFindingsReady,
    firstRunHardTimeout,
    firstRunNotifyWhenReady,
    firstRunSoftTimeout,
    firstRunStartedAt,
    showContent,
    timeoutJob,
    updateJob,
  ]);

  // Reset offset when filters change
  const handleFilterChange = (setter: (v: string) => void) => (value: string) => {
    setter(value);
    setOffset(0);
    setGroupsOffset(0);
  };

  const handleSeverityChange = (value: string | null) => {
    setSeverity(value);
    setOffset(0);
    setGroupsOffset(0);
  };

  const handleSourceChange = (value: string) => {
    setSource(value);
    setOffset(0);
    setGroupsOffset(0);
  };

  const handleManualRefresh = useCallback(async () => {
    const jobId = addJob({
      type: 'findings',
      title: 'Refresh findings',
      message: 'Refreshing findings list...',
      progress: 20,
      status: 'running',
      dedupeKey: `findings-refresh:${effectiveTenantId ?? 'auth'}:${accountId || 'all'}`,
      actorId: user?.id ?? 'anonymous',
      resourceId: accountId || null,
    });
    try {
      if (viewMode === 'grouped') {
        await Promise.all([fetchFindings(), fetchGroups()]);
      } else {
        await fetchFindings();
      }
      completeJob(jobId, 'Findings refreshed.');
    } catch (refreshError) {
      failJob(jobId, 'Refresh failed.', getErrorMessage(refreshError));
    }
  }, [accountId, addJob, completeJob, effectiveTenantId, failJob, fetchFindings, fetchGroups, user?.id, viewMode]);

  const handleRetryFirstRun = async () => {
    if (!firstRunAccountId) return;
    setFirstRunHardTimeout(false);
    setFirstRunSoftTimeout(false);
    setFirstRunFindingsReady(false);
    setFirstRunActionsReady(false);
    setFirstRunStartedAt(Date.now());

    if (firstRunFindingsJobId) {
      updateJob(firstRunFindingsJobId, {
        status: 'running',
        message: 'Retry requested. Restarting findings ingestion...',
        progress: 15,
      });
    }
    if (firstRunActionsJobId) {
      updateJob(firstRunActionsJobId, {
        status: 'running',
        message: 'Retry requested. Restarting action computation...',
        progress: 15,
      });
    }

    try {
      await Promise.all([
        triggerIngest(firstRunAccountId, effectiveTenantId),
        triggerComputeActions({ account_id: firstRunAccountId }, effectiveTenantId),
      ]);
      if (typeof window !== 'undefined') {
        localStorage.setItem(
          FIRST_RUN_STORAGE_KEY,
          JSON.stringify({
            accountId: firstRunAccountId,
            startedAt: Date.now(),
            findingsJobId: firstRunFindingsJobId,
            actionsJobId: firstRunActionsJobId,
          })
        );
      }
      setFirstRunEnabled(true);
    } catch (retryError) {
      if (firstRunFindingsJobId) {
        timeoutJob(firstRunFindingsJobId, 'Retry failed for findings.', getErrorMessage(retryError));
      }
      if (firstRunActionsJobId) {
        timeoutJob(firstRunActionsJobId, 'Retry failed for actions.', getErrorMessage(retryError));
      }
      setError(getErrorMessage(retryError));
    }
  };

  // Get unique regions from accounts
  const allRegions = Array.from(
    new Set(accounts.flatMap((a) => a.regions))
  ).sort();

  const filteredFindings = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return findings;

    return findings.filter((finding) => {
      const haystack = [
        finding.title,
        finding.description,
        finding.finding_id,
        finding.resource_id,
        finding.control_id,
        finding.account_id,
        finding.region,
        finding.effective_status,
        finding.status,
        finding.severity_label,
        finding.source,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();

      return haystack.includes(query);
    });
  }, [findings, searchQuery]);

  const displayedFindings = useMemo(() => {
    if (!remediationFocus) return filteredFindings;
    return filteredFindings.filter(
      (finding) => classifyFindingRemediationFocus(finding) === remediationFocus
    );
  }, [filteredFindings, remediationFocus]);

  const displayedGroups = useMemo(() => {
    if (!remediationFocus) return groups;
    return groups.filter(
      (group) => classifyFindingGroupRemediationFocus(group) === remediationFocus
    );
  }, [groups, remediationFocus]);

  const remediationCounts = useMemo(() => {
    const counts = new Map<RemediationFocusBucket, number>();
    REMEDIATION_FOCUS_ORDER.forEach((bucket) => counts.set(bucket, 0));
    if (viewMode === 'grouped') {
      groups.forEach((group) => {
        const bucket = classifyFindingGroupRemediationFocus(group);
        counts.set(bucket, (counts.get(bucket) || 0) + 1);
      });
      return counts;
    }
    filteredFindings.forEach((finding) => {
      const bucket = classifyFindingRemediationFocus(finding);
      counts.set(bucket, (counts.get(bucket) || 0) + 1);
    });
    return counts;
  }, [filteredFindings, groups, viewMode]);

  const memoizedCounts = useMemo(() => {
    const counts: Record<string, number> = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFORMATIONAL: 0 };
    displayedFindings.forEach((f) => {
      if (f.severity_label && counts[f.severity_label] !== undefined) {
        counts[f.severity_label]++;
      }
    });
    return counts;
  }, [displayedFindings]);

  // Check if top 3 findings should be highlighted (critical/high)
  const highlightedIds = new Set(
    displayedFindings
      .filter((f) => f.severity_label === 'CRITICAL' || f.severity_label === 'HIGH')
      .slice(0, 3)
      .map((f) => f.id)
  );

  const findingsTrackProgress = firstRunFindingsReady
    ? 100
    : firstRunHardTimeout
      ? 100
      : firstRunSoftTimeout
        ? 78
        : 42;
  const actionsTrackProgress = firstRunActionsReady
    ? 100
    : firstRunHardTimeout
      ? 100
      : firstRunSoftTimeout
        ? 64
        : 30;

  const canApplyGroupActions = Boolean(isAuthenticated && user?.role === 'admin');
  const groupActionFilters = useMemo<FindingGroupsFilters>(() => ({
    account_id: accountId || undefined,
    region: region || undefined,
    severity: severity || undefined,
    source: source || undefined,
    status: status || undefined,
    control_id: controlId.trim() || undefined,
    resource_id: resourceId.trim() || undefined,
  }), [accountId, region, severity, source, status, controlId, resourceId]);

  const handleGroupActionComplete = useCallback((result: FindingGroupActionResponse) => {
    const actionLabel = result.action === 'suppress'
      ? 'Suppress Group'
      : result.action === 'acknowledge_risk'
        ? 'Acknowledge Risk'
        : 'Mark as False Positive';
    const message = result.action === 'acknowledge_risk'
      ? `${actionLabel} persisted on ${result.acknowledged_findings} findings${result.status_updates > 0 ? ` (${result.status_updates} status updates)` : ''}.`
      : `${actionLabel} applied to ${result.matched_findings} findings (${result.exceptions_created} created, ${result.exceptions_updated} updated).`;
    setGroupActionNotice({ tone: 'success', message });
    void fetchGroups();
    void fetchFindings();
  }, [fetchFindings, fetchGroups]);

  return (
    <AppShell title="Findings">
      <div className="max-w-6xl mx-auto w-full">
        {!showContent && !isLoading && isAuthenticated && (
          <TenantIdForm onSave={setTenantId} />
        )}

        {/* Filters row and content (when authenticated or tenant ID is set) */}
        {showContent && (
          <>
            {firstRunEnabled && (
              <div className="mb-4 rounded-2xl border border-border bg-surface p-4">
                <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">Preparing your first security workspace</p>
                    <p className="text-xs text-muted">
                      We keep you on Findings while background processing completes.
                      {firstRunSoftTimeout && !firstRunHardTimeout ? ' Showing partial results while actions continue.' : ''}
                    </p>
                  </div>
                  <label className="inline-flex items-center gap-2 text-xs text-muted">
                    <input
                      type="checkbox"
                      checked={firstRunNotifyWhenReady}
                      onChange={(event) => setFirstRunNotifyWhenReady(event.target.checked)}
                    />
                    Notify me when ready
                  </label>
                </div>

                <div className="space-y-3">
                  <div className="rounded-xl border border-border/60 bg-bg/50 p-3">
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <p className="text-sm text-text">Loading findings</p>
                      <span className="text-xs text-muted">
                        {firstRunFindingsReady ? 'Ready' : firstRunHardTimeout ? 'Timed out' : 'Running'}
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-border/80">
                      <div className="h-full rounded-full bg-accent transition-all duration-300" style={{ width: `${findingsTrackProgress}%` }} />
                    </div>
                  </div>

                  <div className="rounded-xl border border-border/60 bg-bg/50 p-3">
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <p className="text-sm text-text">Computing actions</p>
                      <span className="text-xs text-muted">
                        {firstRunActionsReady
                          ? 'Ready'
                          : firstRunHardTimeout
                            ? 'Timed out'
                            : firstRunSoftTimeout
                              ? 'Partial'
                              : 'Running'}
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-border/80">
                      <div className="h-full rounded-full bg-accent transition-all duration-300" style={{ width: `${actionsTrackProgress}%` }} />
                    </div>
                  </div>
                </div>

                {firstRunHardTimeout && (
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-warning/30 bg-warning/10 p-3">
                    <p className="text-xs text-warning">
                      Processing exceeded 15 minutes. You can keep using partial results and retry background jobs.
                    </p>
                    <Button size="sm" variant="secondary" onClick={handleRetryFirstRun}>
                      Retry processing
                    </Button>
                  </div>
                )}
              </div>
            )}
            <BackgroundJobsProgressBanner types={['findings']} />
            {(scopeMetaError || accountsError) && (
              <div className="mb-4 p-4 bg-danger/10 border border-danger/20 rounded-xl">
                <p className="text-sm font-medium text-danger">Some page data failed to load</p>
                {scopeMetaError && (
                  <p className="text-sm text-danger/80">{scopeMetaError}</p>
                )}
                {accountsError && (
                  <p className="text-sm text-danger/80">{accountsError}</p>
                )}
              </div>
            )}
            {/* Unified 3D Control Card */}
            <div className="nm-neu-sm rounded-[2.5rem] p-6 mb-8 space-y-6">
              {/* Row 1: Search, View Toggle, Refresh */}
              <div className="flex flex-col lg:flex-row items-center gap-4">
                {/* Search Box */}
                <div className="relative flex-1 w-full translate-y-[2px]">
                  <PlaceholdersAndVanishInput
                    value={searchQuery}
                    onChange={setSearchQuery}
                    placeholders={[
                      'Search findings by title, control, or resource',
                      'Try: root access key or public S3 bucket',
                      'Filter by finding ID, account, region, or status',
                    ]}
                  />
                  {viewMode === 'grouped' && (
                    <span className="absolute right-[4.5rem] top-1/2 -translate-y-1/2 text-[10px] font-bold uppercase tracking-wider text-muted bg-surface border border-border/60 rounded px-1.5 py-0.5 pointer-events-none hidden sm:block">
                      Flat View Only
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3 shrink-0 w-full lg:w-auto justify-between lg:justify-end">
                  {/* Grouped / Flat view toggle */}
                  <div className="flex items-center rounded-2xl nm-neu-pressed p-1">
                    <button
                      onClick={() => setViewMode('grouped')}
                      className={`px-3 py-1.5 text-sm font-medium rounded-xl transition-all ${viewMode === 'grouped'
                        ? 'nm-neu-sm text-[#4D9BFF] shadow-none'
                        : 'text-muted hover:text-text'
                        }`}
                    >
                      Grouped
                    </button>
                    <button
                      onClick={() => setViewMode('flat')}
                      className={`px-3 py-1.5 text-sm font-medium rounded-xl transition-all ${viewMode === 'flat'
                        ? 'nm-neu-sm text-[#4D9BFF] shadow-none'
                        : 'text-muted hover:text-text'
                        }`}
                    >
                      Flat
                    </button>
                  </div>

                  <Button
                    variant="secondary"
                    onClick={handleManualRefresh}
                    disabled={isLoading}
                    className="rounded-xl px-4 h-[42px]"
                  >
                    <svg
                      className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                      />
                    </svg>
                    Refresh
                  </Button>
                </div>
              </div>              {/* Row 2: Severity and Secondary Actions */}
              <div className="flex flex-wrap xl:flex-nowrap items-end justify-between gap-4 pt-6 border-t border-border/20">
                {/* Left: Severity inline */}
                <div className="flex-shrink-0">
                  <div className="flex flex-wrap items-center gap-4">
                    <SeverityTabs selected={severity} onChange={handleSeverityChange} counts={memoizedCounts} />
                  </div>
                </div>

                {/* Right: Dropdowns and ID Inputs */}
                <div className="flex flex-wrap items-end gap-3 flex-1 justify-start lg:justify-end min-w-[300px]">
                  <div className="w-full sm:w-40">
                    <span className="text-[10px] font-bold uppercase text-muted mb-1 block ml-1">Status</span>
                    <SelectDropdown
                      value={status}
                      onValueChange={handleFilterChange(setStatus)}
                      options={[
                        { value: '', label: 'All Statuses' },
                        { value: DEFAULT_OPEN_FINDINGS_STATUS, label: 'Open' },
                        { value: 'NEW', label: 'New' },
                        { value: 'NOTIFIED', label: 'Notified' },
                        { value: 'RESOLVED', label: 'Resolved' },
                        { value: 'SUPPRESSED', label: 'Suppressed' },
                      ]}
                    />
                  </div>
                  <div className="w-full sm:w-40">
                    <span className="text-[10px] font-bold uppercase text-muted mb-1 block ml-1">Account</span>
                    <SelectDropdown
                      value={accountId}
                      onValueChange={handleFilterChange(setAccountId)}
                      options={[
                        { value: '', label: 'All Accounts' },
                        ...accounts.map((acc) => ({ value: acc.account_id, label: acc.account_id })),
                      ]}
                    />
                  </div>
                  <div className="w-full sm:w-40">
                    <span className="text-[10px] font-bold uppercase text-muted mb-1 block ml-1">Region</span>
                    <SelectDropdown
                      value={region}
                      onValueChange={handleFilterChange(setRegion)}
                      options={[
                        { value: '', label: 'All Regions' },
                        ...allRegions.map((r) => ({ value: r, label: r })),
                      ]}
                    />
                  </div>
                  <div className="flex-1 min-w-[120px]">
                    <span className="text-[10px] font-bold uppercase text-muted mb-1 block ml-1">IDs</span>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={controlId}
                        onChange={(event) => { setControlId(event.target.value); setOffset(0); }}
                        placeholder="Control ID"
                        className="h-10 w-full rounded-xl nm-neu-pressed border-none px-3 text-sm bg-transparent text-text placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent transition-all"
                      />
                      <input
                        type="text"
                        value={resourceId}
                        onChange={(event) => { setResourceId(event.target.value); setOffset(0); }}
                        placeholder="Resource ID"
                        className="h-10 w-full rounded-xl nm-neu-pressed border-none px-3 text-sm bg-transparent text-text placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent transition-all"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-border/20">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted">Remediation queue</span>
                {REMEDIATION_FILTER_OPTIONS.map((bucket) => {
                  const presentation = getRemediationFocusPresentation(bucket);
                  const count = remediationCounts.get(bucket) || 0;
                  const isActive = remediationFocus === bucket;
                  return (
                    <button
                      key={bucket}
                      type="button"
                      onClick={() => setRemediationFocus(isActive ? '' : bucket)}
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-all ${
                        isActive
                          ? 'nm-neu-sm text-accent'
                          : 'nm-neu-pressed text-muted hover:text-text'
                      }`}
                    >
                      {presentation.label} ({count})
                    </button>
                  );
                })}
              </div>

              {/* Row 3: Active filters Footer */}
              {(severity || source || accountId || region || controlId || resourceId || status || searchQuery || remediationFocus) && (
                <div className="pt-4 mt-2 border-t border-border/20 flex flex-wrap items-center gap-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-muted mr-1">Active:</span>
                  {severity && (
                    <div className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-text nm-neu-pressed">
                      Severity: {severity}
                      <button type="button" aria-label="Remove severity filter" onClick={() => handleFilterChange(setSeverity)('')} className="ml-1 text-muted hover:text-text">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  )}
                  {source && (
                    <div className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-text nm-neu-pressed">
                      Source: {getSourceLabel(source)}
                      <button type="button" aria-label="Remove source filter" onClick={() => handleFilterChange(setSource)('')} className="ml-1 text-muted hover:text-text">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  )}
                  {accountId && (
                    <div className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-text nm-neu-pressed">
                      Account: {accountId}
                      <button type="button" aria-label="Remove account filter" onClick={() => handleFilterChange(setAccountId)('')} className="ml-1 text-muted hover:text-text">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  )}
                  {region && (
                    <div className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-text nm-neu-pressed">
                      Region: {region}
                      <button type="button" aria-label="Remove region filter" onClick={() => handleFilterChange(setRegion)('')} className="ml-1 text-muted hover:text-text">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  )}
                  {status && (
                    <div className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-text nm-neu-pressed">
                      Status: {getStatusFilterLabel(status)}
                      <button type="button" aria-label="Remove status filter" onClick={() => handleFilterChange(setStatus)('')} className="ml-1 text-muted hover:text-text">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  )}
                  {controlId && (
                    <div className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-text nm-neu-pressed">
                      Control ID: {controlId}
                      <button type="button" aria-label="Remove control ID filter" onClick={() => { setControlId(''); setOffset(0); }} className="ml-1 text-muted hover:text-text">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  )}
                  {resourceId && (
                    <div className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-text nm-neu-pressed">
                      Resource ID: {resourceId}
                      <button type="button" aria-label="Remove resource ID filter" onClick={() => { setResourceId(''); setOffset(0); }} className="ml-1 text-muted hover:text-text">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  )}
                  {searchQuery && (
                    <div className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-text nm-neu-pressed">
                      Search: {searchQuery}
                      <button type="button" aria-label="Remove search filter" onClick={() => setSearchQuery('')} className="ml-1 text-muted hover:text-text">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  )}
                  {remediationFocus && (
                    <div className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-text nm-neu-pressed">
                      Remediation: {getRemediationFocusPresentation(remediationFocus).label}
                      <button type="button" aria-label="Remove remediation filter" onClick={() => setRemediationFocus('')} className="ml-1 text-muted hover:text-text">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  )}
                  <button
                    onClick={() => {
                      setSeverity(null);
                      setSource('');
                      setAccountId('');
                      setRegion('');
                      setControlId('');
                      setResourceId('');
                      setStatus('');
                      setSearchQuery('');
                      setRemediationFocus('');
                      setOffset(0);
                    }}
                    className="ml-2 text-xs font-medium text-[#4D9BFF] hover:underline"
                  >
                    Clear All
                  </button>
                </div>
              )}

              {/* Row 3: Grouping Controls (only for grouped mode) */}
              <AnimatePresence>
                {viewMode === 'grouped' && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="pt-4 border-t border-border/20"
                  >
                    <GroupingControlBar value={groupingDimensions} onChange={setGroupingDimensions} />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Transition Area / Group Action Notifications */}
            {viewMode === 'grouped' && groupActionNotice && (
              <div
                className={`mb-6 rounded-2xl nm-neu-sm px-6 py-4 text-sm font-medium ${groupActionNotice.tone === 'success' ? 'text-success' : 'text-danger'
                  }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-xl nm-neu-pressed ${groupActionNotice.tone === 'success' ? 'text-success' : 'text-danger'}`}>
                      {groupActionNotice.tone === 'success' ? (
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0-13.5A9.75 9.75 0 112.25 12 9.75 9.75 0 0112 2.25z" />
                        </svg>
                      )}
                    </div>
                    <span>{groupActionNotice.message}</span>
                  </div>
                  <button
                    onClick={() => setGroupActionNotice(null)}
                    className="nm-neu-sm h-8 px-3 rounded-lg text-xs hover:text-accent transition-all"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            )}

            {/* Findings Content (Grouped vs Flat) */}
            {viewMode === 'grouped' ? (
              <>
                {isGroupsLoading && (
                  <div className="space-y-6">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="nm-neu-sm rounded-[2.5rem] p-8 animate-pulse">
                        <div className="h-6 bg-border/40 rounded-xl w-1/3 mb-4" />
                        <div className="h-40 bg-border/20 rounded-2xl w-full" />
                      </div>
                    ))}
                  </div>
                )}
                {!isGroupsLoading && groupsError && (
                  <div className="nm-neu-sm rounded-[2.5rem] p-8 text-center">
                    <p className="text-danger font-semibold mb-4">Failed to load grouped findings</p>
                    <Button variant="secondary" onClick={fetchGroups}>Retry</Button>
                  </div>
                )}
                {!isGroupsLoading && !groupsError && displayedGroups.length === 0 && (
                  <div className="nm-neu-sm rounded-[2.5rem] p-12 text-center">
                    <h3 className="text-lg font-bold mb-2">No groups found</h3>
                    <p className="text-muted">Adjust your filters to see more results.</p>
                  </div>
                )}
                {!isGroupsLoading && !groupsError && displayedGroups.length > 0 && (
                  <>
                    <GroupedFindingsView
                      groups={displayedGroups}
                      groupingDimensions={groupingDimensions}
                      effectiveTenantId={effectiveTenantId}
                      onActionSelect={setSelectedActionId}
                      groupActionFilters={groupActionFilters}
                      onGroupActionComplete={handleGroupActionComplete}
                      groupActionsEnabled={canApplyGroupActions}
                    />
                    <div className="mt-8">
                      <Pagination offset={groupsOffset} limit={LIMIT} total={groupsTotal} onPageChange={setGroupsOffset} />
                    </div>
                  </>
                )}
              </>
            ) : (
              <>
                {isLoading && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {[1, 2, 3, 4].map((i) => (
                      <div key={i} className="nm-neu-sm rounded-[2.5rem] p-8 animate-pulse h-64" />
                    ))}
                  </div>
                )}
                {!isLoading && error && (
                  <div className="nm-neu-sm rounded-[2.5rem] p-8 text-center">
                    <p className="text-danger font-semibold mb-4">Error: {error}</p>
                    <Button variant="secondary" onClick={fetchFindings}>Retry</Button>
                  </div>
                )}
                {!isLoading && !error && displayedFindings.length === 0 && (
                  <div className="nm-neu-sm rounded-[2.5rem] p-12 text-center">
                    <h3 className="text-lg font-bold mb-2">No findings found</h3>
                    <p className="text-muted">Try clearing your filters.</p>
                  </div>
                )}
                {!isLoading && !error && displayedFindings.length > 0 && (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                      {displayedFindings.map((finding) => (
                        <FindingCard
                          key={finding.id}
                          finding={finding}
                          isHighlighted={highlightedIds.has(finding.id)}
                          onActionSelect={setSelectedActionId}
                        />
                      ))}
                    </div>
                    <div className="mt-8">
                      <Pagination offset={offset} limit={LIMIT} total={total} onPageChange={setOffset} />
                    </div>
                  </>
                )}
              </>
            )}
          </>
        )}
      </div>

      <ActionDetailModal
        actionId={selectedActionId}
        isOpen={!!selectedActionId}
        onClose={() => setSelectedActionId(null)}
      />
    </AppShell>
  );
}

export default function FindingsPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="Findings">
          <div className="max-w-6xl mx-auto w-full rounded-xl border border-border bg-surface p-6 text-sm text-muted">
            Loading findings...
          </div>
        </AppShell>
      }
    >
      <FindingsPageContent />
    </Suspense>
  );
}
