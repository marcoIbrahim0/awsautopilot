'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { motion } from 'motion/react';
import {
  cancelRemediationRun,
  getErrorMessage,
  getRemediationRun,
  getRemediationRunExecution,
  RemediationArtifactLink,
  RemediationClosureChecklistItem,
  RemediationEvidencePointer,
  RemediationRunDetail,
  RemediationRunExecutionDetail,
  resendRemediationRun,
} from '@/lib/api';
import { downloadPrBundleZip } from '@/lib/pr-bundle-download';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Tabs } from '@/components/ui/Tabs';
import { MultiStepLoader } from '@/components/ui/MultiStepLoader';
import { ExplainerHint } from '@/components/ui/ExplainerHint';
import { RemediationPromptRow } from '@/components/ui/remediation-surface';
import { logError } from '@/lib/errorLogger';
import { cn } from '@/lib/utils';
import {
  getEvidenceCardId,
  resolveEvidenceNavigationHref,
  resolveRunSectionHref,
} from '@/components/remediationRunLinks';

const POLL_INTERVAL_MS = 2500;
const PENDING_STALE_MS = 2 * 60 * 1000; // 2 minutes
const TERMINAL_STATUSES = new Set(['success', 'failed', 'cancelled']);

const RUN_PANEL_CLASS =
  'rounded-[2rem] border border-[var(--border-card)] bg-[var(--card)] shadow-[0_26px_64px_-38px_rgba(15,23,42,0.46)] backdrop-blur-xl';
const RUN_HERO_CLASS =
  'rounded-[2.25rem] border border-accent/18 bg-[linear-gradient(180deg,rgba(255,255,255,0.16),rgba(255,255,255,0)),radial-gradient(circle_at_top_left,rgba(10,113,255,0.16),transparent_34%),radial-gradient(circle_at_top_right,rgba(15,46,155,0.12),transparent_38%),var(--card-hero)] shadow-[0_30px_78px_-40px_rgba(10,48,145,0.4)] backdrop-blur-xl';
const RUN_INSET_CLASS =
  'rounded-[1.5rem] border border-[var(--border-soft)] bg-[var(--card-inset)] shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]';
const RUN_CONTROL_CLASS =
  'rounded-[1.2rem] border border-[var(--border-soft)] bg-[var(--control-bg)] shadow-[inset_0_1px_0_rgba(255,255,255,0.16)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]';
const RUN_PILL_CLASS =
  'rounded-full border border-[var(--border-soft)] bg-[var(--control-bg)] px-3 py-1 text-xs font-semibold text-text';
const RUN_LINK_BUTTON_CLASS =
  'inline-flex items-center justify-center rounded-full border border-[var(--border-soft)] bg-[var(--control-bg)] px-4 py-2 text-sm font-medium text-accent transition-all hover:border-[var(--border-strong)] hover:bg-[var(--control-hover)] hover:text-accent-hover';

function runPanelClass(className?: string) {
  return cn(RUN_PANEL_CLASS, className);
}

function runInsetClass(className?: string) {
  return cn(RUN_INSET_CLASS, className);
}

function runControlClass(className?: string) {
  return cn(RUN_CONTROL_CLASS, className);
}

function getProgressPercent(status: string): number {
  switch (status?.toLowerCase()) {
    case 'pending':
      return 15;
    case 'running':
      return 50;
    case 'awaiting_approval':
      return 75;
    case 'success':
      return 100;
    case 'failed':
    case 'cancelled':
      return 100;
    default:
      return 0;
  }
}

function getStatusBadgeVariant(status: string): 'success' | 'warning' | 'danger' | 'info' | 'default' {
  switch (status?.toLowerCase()) {
    case 'success':
      return 'success';
    case 'failed':
    case 'cancelled':
      return 'danger';
    case 'running':
      return 'info';
    case 'awaiting_approval':
      return 'warning';
    case 'pending':
      return 'warning';
    default:
      return 'default';
  }
}

function getStatusLogMessage(status: string, mode: string): string {
  const isBundleGeneration = mode === 'pr_only';
  switch (status?.toLowerCase()) {
    case 'pending':
      return isBundleGeneration ? 'Bundle generation queued, waiting for worker…' : 'Run queued, waiting for worker…';
    case 'running':
      return isBundleGeneration ? 'Worker generating bundle…' : 'Worker processing…';
    case 'awaiting_approval':
      return 'SaaS apply is archived. Download the bundle and continue in your own pipeline.';
    case 'success':
      return 'Completed successfully.';
    case 'failed':
    case 'cancelled':
      return isBundleGeneration ? 'Generation finished.' : 'Run finished.';
    default:
      return isBundleGeneration ? 'Initializing generation…' : 'Initializing…';
  }
}

function getProgressHeading(mode: string): string {
  return mode === 'pr_only' ? 'Bundle progress' : 'Remediation progress';
}

function withTenantQuery(path: string, tenantId?: string): string {
  if (!tenantId || !path.startsWith('/')) return path;
  const [pathname, hash] = path.split('#', 2);
  const params = new URLSearchParams();
  params.set('tenant_id', tenantId);
  return `${pathname}?${params.toString()}${hash ? `#${hash}` : ''}`;
}

function getChecklistBadgeVariant(status: string): 'success' | 'warning' | 'danger' | 'default' {
  switch (status?.toLowerCase()) {
    case 'complete':
      return 'success';
    case 'failed':
      return 'danger';
    case 'pending':
      return 'warning';
    default:
      return 'default';
  }
}

function getChecklistStatusLabel(status: string): string {
  switch (status?.toLowerCase()) {
    case 'complete':
      return 'complete';
    case 'failed':
      return 'failed';
    case 'pending':
      return 'pending';
    default:
      return status || 'unknown';
  }
}

function getArtifactMetaSummary(artifact: RemediationArtifactLink): string | null {
  const metadata = artifact.metadata ?? {};
  if (artifact.kind === 'bundle') {
    const formatName = typeof metadata.format === 'string' ? metadata.format : null;
    const fileCount =
      typeof metadata.file_count === 'number' && Number.isFinite(metadata.file_count)
        ? metadata.file_count
        : null;
    if (formatName && fileCount !== null) {
      return `${formatName} · ${fileCount} file${fileCount === 1 ? '' : 's'}`;
    }
  }
  if (artifact.kind === 'change_summary') {
    const changeCount =
      typeof metadata.change_count === 'number' && Number.isFinite(metadata.change_count)
        ? metadata.change_count
        : null;
    const appliedBy = typeof metadata.applied_by === 'string' ? metadata.applied_by : null;
    if (changeCount !== null && appliedBy) {
      return `${changeCount} change${changeCount === 1 ? '' : 's'} · ${appliedBy}`;
    }
  }
  if (artifact.kind === 'direct_fix') {
    const logCount =
      typeof metadata.log_count === 'number' && Number.isFinite(metadata.log_count)
        ? metadata.log_count
        : null;
    if (logCount !== null) {
      return `${metadata.post_check_passed === true ? 'post-check passed' : 'post-check pending'} · ${logCount} log line${logCount === 1 ? '' : 's'}`;
    }
  }
  return null;
}

function buildReviewCueItems(
  implementationArtifacts: RemediationArtifactLink[],
  evidencePointers: RemediationEvidencePointer[],
  closureChecklist: RemediationClosureChecklistItem[]
): Array<{ detail: string; id: string; title: string }> {
  const artifactCues = implementationArtifacts.map((artifact) => ({
    detail: artifact.description,
    id: `artifact-${artifact.key}`,
    title: artifact.label,
  }));
  const evidenceCues = evidencePointers.map((pointer) => ({
    detail: pointer.description,
    id: `evidence-${pointer.key}`,
    title: pointer.label,
  }));
  const checklistCues = closureChecklist.map((item) => ({
    detail: item.detail,
    id: `checklist-${item.id}`,
    title: item.title,
  }));
  return [...artifactCues, ...evidenceCues, ...checklistCues];
}

function getRunModeLabel(mode: string): string {
  return mode.replace(/_/g, ' ');
}

function formatLocalTimestamp(value: string | null): string | null {
  return value ? new Date(value).toLocaleString() : null;
}

function getRunSummaryText(run: RemediationRunDetail): string {
  switch (run.status) {
    case 'success':
      return run.mode === 'pr_only'
        ? 'The remediation bundle is ready for review, apply, and closure verification.'
        : 'The direct fix completed. Recompute the action to confirm closure.';
    case 'failed':
      return run.mode === 'pr_only'
        ? 'Bundle generation stopped before closure was verified. Review the activity and evidence before retrying.'
        : 'The run stopped before closure was verified. Review the activity and evidence before retrying.';
    case 'cancelled':
      return run.mode === 'pr_only'
        ? 'Bundle generation was cancelled. Review the recorded state before starting a new generation.'
        : 'The run was cancelled. Review the recorded state before starting a new remediation run.';
    case 'awaiting_approval':
      return 'SaaS-managed PR-bundle apply is archived. Download the bundle and run it in your own pipeline or with customer-owned credentials.';
    case 'running':
      return run.mode === 'pr_only'
        ? 'The worker is actively generating this remediation bundle.'
        : 'The worker is actively processing this remediation run.';
    default:
      return run.mode === 'pr_only'
        ? 'Bundle generation is queued and waiting for worker capacity.'
        : 'This remediation run is queued and waiting for worker capacity.';
  }
}

function hasGeneratedFiles(run: RemediationRunDetail, compact: boolean): boolean {
  if (compact || run.status !== 'success' || run.mode !== 'pr_only') {
    return false;
  }
  const artifacts = run.artifacts as { pr_bundle?: { files?: { path: string; content: string }[] } } | null;
  return Boolean(artifacts?.pr_bundle?.files?.length);
}

interface RemediationRunProgressProps {
  runId: string;
  tenantId?: string;
  onComplete?: () => void;
  compact?: boolean;
  /** Use full-width layout with content across columns (remediation run detail page). */
  fullWidth?: boolean;
}

export function RemediationRunProgress({
  runId,
  tenantId,
  onComplete,
  compact = false,
  fullWidth = false,
}: RemediationRunProgressProps) {
  const [run, setRun] = useState<RemediationRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [execution, setExecution] = useState<RemediationRunExecutionDetail | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);

  const applyExecutionSnapshot = useCallback((data: RemediationRunExecutionDetail) => {
    if (data.source === 'run_fallback') {
      setExecution(null);
      setExecutionError(null);
      return;
    }
    setExecution(data);
    setExecutionError(null);
  }, []);

  useEffect(() => {
    if (!runId) return;

    const fetchRun = async () => {
      try {
        const data = await getRemediationRun(runId, tenantId);
        setRun(data);
        setError(null);
        setPollError(null);
        if (TERMINAL_STATUSES.has(data.status) && onComplete) {
          onComplete();
        }
      } catch (err) {
        setError(getErrorMessage(err));
      }
    };

    fetchRun();

    const interval = setInterval(() => {
      getRemediationRun(runId, tenantId)
        .then((data) => {
          setRun(data);
          setPollError(null);
          if (TERMINAL_STATUSES.has(data.status)) {
            clearInterval(interval);
            onComplete?.();
          }
        })
        .catch((err) => {
          const errorToLog = err instanceof Error ? err : new Error('Failed to poll remediation run');
          logError(errorToLog, {
            file: 'frontend/src/components/RemediationRunProgress.tsx',
            operation: 'pollRemediationRun',
            runId,
            tenantId: tenantId ?? 'auth-session',
          });
          setPollError('Unable to refresh run status. Retrying...');
        });
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [runId, tenantId, onComplete]);

  useEffect(() => {
    let active = true;
    const fetchExecution = async () => {
      try {
        const data = await getRemediationRunExecution(runId);
        if (!active) return;
        applyExecutionSnapshot(data);
      } catch (err) {
        if (!active) return;
        const e = err as { status?: number };
        if (e?.status === 401 || e?.status === 404) {
          setExecution(null);
          return;
        }
        setExecutionError(getErrorMessage(err));
      }
    };
    fetchExecution();
    const interval = setInterval(fetchExecution, POLL_INTERVAL_MS);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [runId, applyExecutionSnapshot]);

  if (error) {
    return (
      <div className="p-4 bg-danger/10 border border-danger/20 rounded-xl">
        <p className="text-sm text-danger">{error}</p>
      </div>
    );
  }

  if (!run) {
    return (
      <div className={cn(runPanelClass('p-6 rounded-2xl animate-pulse'), 'border-[var(--border-soft)]')}>
        <div className="h-6 bg-border rounded w-1/3 mb-4" />
        <div className="h-4 bg-border rounded w-full mb-2" />
        <div className="h-4 bg-border rounded w-2/3" />
      </div>
    );
  }

  const isTerminal = TERMINAL_STATUSES.has(run.status);
  const progressPercent = getProgressPercent(run.status);
  const artifactMetadata = run.artifact_metadata ?? {
    implementation_artifacts: [],
    evidence_pointers: [],
    closure_checklist: [],
  };
  const implementationArtifacts = artifactMetadata.implementation_artifacts ?? [];
  const evidencePointers = artifactMetadata.evidence_pointers ?? [];
  const closureChecklist = artifactMetadata.closure_checklist ?? [];
  const evidenceByKey = new Map(evidencePointers.map((pointer) => [pointer.key, pointer]));
  const actionHref = run.action ? withTenantQuery(`/actions/${run.action.id}`, tenantId) : withTenantQuery('/actions', tenantId);
  const generatedFilesVisible = hasGeneratedFiles(run, compact);
  const showImplementationArtifacts = !compact && !fullWidth && implementationArtifacts.length > 0;
  const modeLabel = getRunModeLabel(run.mode);
  const createdAtLabel = formatLocalTimestamp(run.created_at);
  const startedAtLabel = formatLocalTimestamp(run.started_at);
  const completedAtLabel = formatLocalTimestamp(run.completed_at);
  const runSummaryText = getRunSummaryText(run);
  const isBundleGeneration = run.mode === 'pr_only';
  const progressHeading = getProgressHeading(run.mode);
  const snapshotLabel = isBundleGeneration ? 'Bundle snapshot' : 'Run snapshot';
  const summaryEyebrow = isBundleGeneration ? 'Bundle generation' : 'Remediation run';
  const detailHeading = isBundleGeneration ? 'Generation details' : 'Technical details';
  const idLabel = isBundleGeneration ? 'Generation ID' : 'Run ID';
  const cancelLabel = isBundleGeneration ? 'Cancel generation' : 'Cancel run';
  const checklistCompleteCount = closureChecklist.filter((item) => item.status === 'complete').length;
  const prBundleFiles =
    generatedFilesVisible
      ? (((run.artifacts as { pr_bundle?: { files?: { path: string; content: string }[] } } | null)?.pr_bundle?.files) ?? [])
      : [];
  const reviewCueItems = buildReviewCueItems(
    implementationArtifacts,
    evidencePointers,
    closureChecklist
  );
  const steps = [
    { key: 'pending', label: 'Pending', done: run.status !== 'pending' },
    { key: 'running', label: 'Running', done: isTerminal || run.status === 'running' },
    {
      key: 'done',
      label:
        run.status === 'success'
          ? 'Success'
          : run.status === 'failed'
            ? 'Failed'
            : run.status === 'cancelled'
              ? 'Cancelled'
              : 'Complete',
      done: isTerminal,
    },
  ];

  // Build log lines for display (status + backend logs)
  const logLines: string[] = [getStatusLogMessage(run.status, run.mode)];
  if (run.logs) {
    logLines.push(...run.logs.split('\n').filter(Boolean));
  }

  const isPendingStale =
    (run.status === 'pending' || run.status === 'running') &&
    Date.now() - new Date(run.created_at).getTime() > PENDING_STALE_MS;

  const canCancel = run.status === 'pending' || run.status === 'running' || run.status === 'awaiting_approval';

  const handleDownloadBundle = async () => {
    if (!prBundleFiles.length) return;
    setDownloadError(null);
    setDownloadLoading(true);
    try {
      await downloadPrBundleZip(run.id, prBundleFiles);
    } catch (err) {
      setDownloadError(getErrorMessage(err));
    } finally {
      setDownloadLoading(false);
    }
  };

  const handleCancel = async () => {
    setCancelLoading(true);
    try {
      const updated = await cancelRemediationRun(runId, tenantId);
      setRun(updated);
      onComplete?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setCancelLoading(false);
    }
  };

  const isLoadingRun = run.status === 'pending' || run.status === 'running';
  const loaderSteps = [
    { key: 'pending', label: 'Queued', done: run.status !== 'pending', active: run.status === 'pending' },
    { key: 'running', label: 'Generating', done: isTerminal || run.status === 'running', active: run.status === 'running' },
    {
      key: 'done',
      label: run.status === 'success' ? 'Complete' : run.status === 'failed' || run.status === 'cancelled' ? 'Done' : 'Complete',
      done: isTerminal,
      failed: run.status === 'failed' || run.status === 'cancelled',
    },
  ];

  const executionFolders =
    (execution?.results?.folders as
      | { folder: string; status: string; error?: string; commands?: { command: string; returncode: number; stdout: string; stderr: string }[] }[]
      | undefined) ?? [];
  const executionFailFast =
    typeof (execution?.workspace_manifest as { fail_fast?: unknown } | null)?.fail_fast === 'boolean';

  const prOnlyGuideTabs = [
    {
      title: 'Pipeline (Terraform)',
      value: 'pipeline-terraform',
      content: (
        <div className="space-y-2">
          <p><strong className="text-text">Terraform</strong> is a tool that creates or updates cloud resources from <code className="text-xs">.tf</code> files. If this is your first time, follow these steps.</p>
          <ol className="list-decimal list-inside space-y-1.5 ml-1">
            <li>Download the bundle and unzip it. You should see <code className="text-xs">.tf</code> files such as <code className="text-xs">main.tf</code> and <code className="text-xs">providers.tf</code>.</li>
            <li>Install Terraform on the machine that runs your pipeline (for example, the <a href="https://developer.hashicorp.com/terraform/install" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">HashiCorp install guide</a>).</li>
            <li>Put the unzipped files into your infrastructure Git repo on a new branch, then commit and push.</li>
            <li>Configure the pipeline to use the same AWS account and region as this action with the right AWS credentials and <code className="text-xs">AWS_REGION</code> or <code className="text-xs">TF_VAR_region</code>.</li>
            <li>Run <code className="text-xs">terraform init</code>, then <code className="text-xs">terraform plan</code>, then <code className="text-xs">terraform apply -auto-approve</code>. Add a manual approval step between plan and apply if needed.</li>
            <li>Trigger the pipeline so the remediation is applied in the correct environment.</li>
          </ol>
        </div>
      ),
    },
    {
      title: 'Merge PR',
      value: 'merge-pr',
      content: (
        <div className="space-y-2">
          <p><strong className="text-text">A Pull Request (PR)</strong> lets you propose the remediation in your infrastructure repo before it lands on the default branch.</p>
          <ol className="list-decimal list-inside space-y-1.5 ml-1">
            <li>Download and unzip the bundle, then create a new branch in your infrastructure repo.</li>
            <li>Copy the files into the repo, run <code className="text-xs">git add .</code>, and commit them with a remediation-specific message.</li>
            <li>Push the branch and open a PR or MR to your default branch.</li>
            <li>After approval, merge it into the branch that already runs your Terraform pipeline.</li>
            <li>Make sure that pipeline uses the same AWS account and region as this action.</li>
          </ol>
        </div>
      ),
    },
  ];

  if (fullWidth) {
    const jumpLinks = [
      { href: '#run-summary', label: 'Summary' },
      { href: '#run-what-next', label: 'What you need to do' },
      { href: '#run-closure', label: 'Closure proof' },
      { href: '#run-technical-details', label: detailHeading },
      { href: '#run-activity', label: 'Activity log' },
    ];

    if (generatedFilesVisible) {
      jumpLinks.push({ href: '#run-generated-files', label: 'Generated files' });
    }

    return (
      <div className="grid grid-cols-1 xl:grid-cols-[320px_minmax(0,1fr)] gap-6 items-start">
        <aside className="min-w-0 xl:sticky xl:top-24">
          <div className={cn(runPanelClass(), 'p-5 space-y-5')}>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.24em] text-muted">{snapshotLabel}</p>
              <p className="mt-2 text-sm text-muted">Use this rail to orient yourself, then work top to bottom through the page.</p>
            </div>

            <div className={runInsetClass('px-4 py-4')}>
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-muted">
                  Status
                  <ExplainerHint content={{ conceptId: 'run_status', context: 'run' }} label="Status" iconOnly />
                </span>
                <Badge variant={getStatusBadgeVariant(run.status)}>{run.status}</Badge>
              </div>
              <p className="mt-3 text-lg font-semibold text-text capitalize">{modeLabel}</p>
              <p className="mt-1 text-sm text-muted leading-relaxed">{runSummaryText}</p>
            </div>

            {run.action && (
              <div className={runInsetClass('px-4 py-4')}>
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">Action</p>
                <Link href={actionHref} className="mt-3 block text-base font-semibold text-accent hover:text-accent-hover transition-colors">
                  {run.action.title}
                </Link>
                <p className="mt-2 text-xs font-mono text-muted">{run.action.account_id}{run.action.region ? ` · ${run.action.region}` : ''}</p>
                {run.action.status && (
                  <p className="mt-2 text-xs text-muted">Action status: <span className="font-semibold text-text">{run.action.status}</span></p>
                )}
              </div>
            )}

            <div className={runInsetClass('px-4 py-4')}>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">Metadata</p>
              <dl className="mt-3 space-y-3 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-muted">{idLabel}</dt>
                  <dd className="font-mono text-xs text-text text-right break-all">{run.id}</dd>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-muted">Created</dt>
                  <dd className="text-text text-right">{createdAtLabel ?? 'Not recorded'}</dd>
                </div>
                {startedAtLabel && (
                  <div className="flex items-start justify-between gap-3">
                    <dt className="text-muted">Started</dt>
                    <dd className="text-text text-right">{startedAtLabel}</dd>
                  </div>
                )}
                {completedAtLabel && (
                  <div className="flex items-start justify-between gap-3">
                    <dt className="text-muted">Completed</dt>
                    <dd className="text-text text-right">{completedAtLabel}</dd>
                  </div>
                )}
                {closureChecklist.length > 0 && (
                  <div className="flex items-start justify-between gap-3">
                    <dt className="inline-flex items-center gap-2 text-muted">
                      Checks complete
                      <ExplainerHint content={{ conceptId: 'closure_checklist', context: 'run' }} label="Checks complete" iconOnly />
                    </dt>
                    <dd className="text-text text-right">{checklistCompleteCount}/{closureChecklist.length}</dd>
                  </div>
                )}
                {evidencePointers.length > 0 && (
                  <div className="flex items-start justify-between gap-3">
                    <dt className="inline-flex items-center gap-2 text-muted">
                      Evidence
                      <ExplainerHint content={{ conceptId: 'evidence_pointers', context: 'run' }} label="Evidence" iconOnly />
                    </dt>
                    <dd className="text-text text-right">{evidencePointers.length} pointer{evidencePointers.length === 1 ? '' : 's'}</dd>
                  </div>
                )}
              </dl>
            </div>

            <div className={runInsetClass('px-4 py-4')}>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">Jump to</p>
              <div className="mt-3 flex flex-col gap-2">
                {jumpLinks.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    className="rounded-xl px-3 py-2 text-sm font-medium text-muted transition-colors hover:bg-[var(--control-hover)] hover:text-text"
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            </div>
          </div>
        </aside>

        <div className="min-w-0 space-y-6">
          <section
            id="run-summary"
            className={cn(RUN_HERO_CLASS, 'p-6')}
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="max-w-3xl">
                <p className="text-xs font-bold uppercase tracking-[0.28em] text-muted">{summaryEyebrow}</p>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <h2 className="text-3xl font-semibold text-text leading-tight">
                    {run.action?.title ?? `${isBundleGeneration ? 'Generation' : 'Run'} ${run.id.slice(0, 8)}`}
                  </h2>
                  <ExplainerHint content={{ conceptId: 'remediation_run', context: 'run' }} label={summaryEyebrow} iconOnly />
                </div>
                <p className="mt-3 text-base text-muted leading-relaxed">{runSummaryText}</p>
              </div>
              <Badge variant={getStatusBadgeVariant(run.status)} className="px-3 py-1 text-sm capitalize">
                {run.status}
              </Badge>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              <span className={cn(RUN_PILL_CLASS, 'capitalize')}>{modeLabel}</span>
              <ExplainerHint content={{ conceptId: 'run_mode', context: 'run' }} label="Run mode" iconOnly className={RUN_PILL_CLASS} />
              {run.action?.status && (
                <span className={RUN_PILL_CLASS}>
                  Action {run.action.status}
                </span>
              )}
              {closureChecklist.length > 0 && (
                <span className={RUN_PILL_CLASS}>
                  {checklistCompleteCount}/{closureChecklist.length} checks complete
                </span>
              )}
              {evidencePointers.length > 0 && (
                <span className={RUN_PILL_CLASS}>
                  {evidencePointers.length} evidence item{evidencePointers.length === 1 ? '' : 's'}
                </span>
              )}
            </div>

            {!isTerminal && (
              <div className="mt-6">
                <div className="flex justify-between text-xs font-semibold text-muted mb-2">
                  <span className="uppercase tracking-wide">{progressHeading}</span>
                  <ExplainerHint content={{ conceptId: 'progress_state', context: 'run' }} label={progressHeading} iconOnly />
                  <span>{progressPercent}%</span>
                </div>
                <div className={runControlClass('h-2.5 overflow-hidden p-0.5 rounded-full')}>
                  <motion.div
                    className="h-full rounded-full bg-tab-active shadow-[0_10px_22px_-14px_rgba(10,48,145,0.88)]"
                    initial={{ width: 0 }}
                    animate={{ width: `${progressPercent}%` }}
                    transition={{ duration: 0.4, ease: 'easeOut' }}
                  />
                </div>
              </div>
            )}

            {pollError && (
              <div className="mt-5 rounded-2xl border border-danger/20 bg-danger/10 px-4 py-3">
                <p className="text-sm font-semibold text-danger">Live updates are temporarily stale</p>
                <p className="mt-1 text-xs text-danger/80">{pollError}</p>
              </div>
            )}

            <div className="mt-6 flex flex-wrap gap-3">
              {generatedFilesVisible && (
                <Button variant="accent" size="sm" disabled={downloadLoading} onClick={() => { void handleDownloadBundle(); }}>
                  {downloadLoading ? 'Downloading…' : 'Download bundle'}
                </Button>
              )}
              {run.action && (
                <Link
                  href={actionHref}
                  className={RUN_LINK_BUTTON_CLASS}
                >
                  Open action
                </Link>
              )}
              <a
                href="#run-closure"
                className={RUN_LINK_BUTTON_CLASS}
              >
                Review closure proof
              </a>
              {canCancel && (
                <Button variant="ghost" size="sm" onClick={handleCancel} disabled={cancelLoading} className="ml-auto">
                  {cancelLoading ? 'Cancelling…' : cancelLabel}
                </Button>
              )}
            </div>
          </section>

          <section id="run-what-next" className={cn(runPanelClass(), 'p-6')}>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-muted">What you need to do</p>
                <h3 className="mt-2 text-2xl font-semibold text-text">Next action</h3>
              </div>
              {startedAtLabel && (
                <p className="text-xs text-muted">Started {startedAtLabel}{completedAtLabel ? ` · Completed ${completedAtLabel}` : ''}</p>
              )}
            </div>

            {run.status === 'success' && run.mode === 'pr_only' ? (
              <>
                <div className="mt-5 grid gap-4 md:grid-cols-3">
                  <div className={runInsetClass('p-4')}>
                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">01 Review</p>
                    <h4 className="mt-3 text-lg font-semibold text-text">Review the bundle before apply</h4>
                    <p className="mt-2 text-sm text-muted leading-relaxed">Download the generated files, confirm the targeted resources, and review the recorded evidence before this change reaches your infrastructure workflow.</p>
                    {reviewCueItems.length > 0 && (
                      <div className="mt-4 space-y-3">
                        {reviewCueItems.map((item) => (
                          <RemediationPromptRow
                            key={item.id}
                            title={item.title}
                            description={item.detail}
                          />
                        ))}
                      </div>
                    )}
                    {generatedFilesVisible ? (
                      <Button variant="secondary" size="sm" className="mt-4" disabled={downloadLoading} onClick={() => { void handleDownloadBundle(); }}>
                        {downloadLoading ? 'Downloading…' : 'Download bundle'}
                      </Button>
                    ) : (
                      <a href="#run-technical-details" className="mt-4 inline-flex text-sm font-medium text-accent hover:text-accent-hover transition-colors">
                        {isBundleGeneration ? 'Open generation details' : 'Open technical details'}
                      </a>
                    )}
                  </div>
                  <div className={runInsetClass('p-4')}>
                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">02 Apply</p>
                    <h4 className="mt-3 text-lg font-semibold text-text">Ship it through your infra workflow</h4>
                    <p className="mt-2 text-sm text-muted leading-relaxed">Merge it into the repo and pipeline that already manages this AWS account and region, then run Terraform plan and apply.</p>
                    <a href="#run-apply-guide" className="mt-4 inline-flex text-sm font-medium text-accent hover:text-accent-hover transition-colors">
                      Open apply guide
                    </a>
                  </div>
                  <div className={runInsetClass('p-4')}>
                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">03 Verify</p>
                    <h4 className="mt-3 text-lg font-semibold text-text">Confirm the action closes</h4>
                    <p className="mt-2 text-sm text-muted leading-relaxed">After apply, return to the action and recompute actions or trigger a fresh ingest to verify the finding is no longer open.</p>
                    {run.action && (
                      <Link href={actionHref} className="mt-4 inline-flex text-sm font-medium text-accent hover:text-accent-hover transition-colors">
                        Open action
                      </Link>
                    )}
                  </div>
                </div>
                {downloadError && (
                  <p className="mt-4 text-sm text-danger" role="alert">{downloadError}</p>
                )}
              </>
            ) : run.status === 'success' ? (
              <div className={cn('mt-5 p-5', RUN_INSET_CLASS)}>
                <p className="text-sm text-muted leading-relaxed">The direct fix completed. Your next job is to confirm the parent action resolves after a recompute or fresh ingest.</p>
                {run.action && (
                  <Link href={actionHref} className="mt-4 inline-flex text-sm font-medium text-accent hover:text-accent-hover transition-colors">
                    Open action and recompute
                  </Link>
                )}
              </div>
            ) : run.status === 'failed' || run.status === 'cancelled' ? (
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div className={runInsetClass('p-4')}>
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">Review</p>
                  <h4 className="mt-3 text-lg font-semibold text-text">Inspect the recorded failure</h4>
                  <p className="mt-2 text-sm text-muted leading-relaxed">Start with the activity log and closure proof below to understand where the run stopped and what evidence was captured.</p>
                  <a href="#run-activity" className="mt-4 inline-flex text-sm font-medium text-accent hover:text-accent-hover transition-colors">
                    Open activity log
                  </a>
                </div>
                <div className={runInsetClass('p-4')}>
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">Retry</p>
                  <h4 className="mt-3 text-lg font-semibold text-text">Prepare the next run</h4>
                  <p className="mt-2 text-sm text-muted leading-relaxed">Reopen the parent action, correct any missing prerequisites, and create a fresh remediation run once the blocker is resolved.</p>
                  {run.action && (
                    <Link href={actionHref} className="mt-4 inline-flex text-sm font-medium text-accent hover:text-accent-hover transition-colors">
                      Open action
                    </Link>
                  )}
                </div>
              </div>
            ) : (
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div className={runInsetClass('p-4')}>
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">Monitor</p>
                  <h4 className="mt-3 text-lg font-semibold text-text">Let the run finish</h4>
                  <p className="mt-2 text-sm text-muted leading-relaxed">This run is still in flight. Use the activity log and progress details below if you want to watch it live.</p>
                </div>
                <div className={runInsetClass('p-4')}>
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">Intervene</p>
                  <h4 className="mt-3 text-lg font-semibold text-text">Resend only if it stalls</h4>
                  <p className="mt-2 text-sm text-muted leading-relaxed">
                    {isPendingStale ? 'The run has been queued for longer than expected. Resend it to push it back onto the worker queue.' : 'If the run stays queued for more than a couple of minutes, resend it from here.'}
                  </p>
                  {isPendingStale && (
                    <Button
                      variant="secondary"
                      size="sm"
                      className="mt-4"
                      disabled={resendLoading}
                      onClick={async () => {
                        setResendMessage(null);
                        setResendLoading(true);
                        try {
                          await resendRemediationRun(runId, tenantId);
                          setResendMessage('Job re-sent to queue. Worker should pick it up shortly.');
                        } catch (err) {
                          setResendMessage(getErrorMessage(err) || 'Failed to resend.');
                        } finally {
                          setResendLoading(false);
                        }
                      }}
                    >
                      {resendLoading ? 'Sending…' : 'Resend to queue'}
                    </Button>
                  )}
                  {resendMessage && <p className="mt-3 text-xs text-accent">{resendMessage}</p>}
                </div>
              </div>
            )}
          </section>

          <section id="run-closure" className={cn(runPanelClass(), 'p-6')}>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-muted">Closure proof</p>
                <h3 className="mt-2 text-2xl font-semibold text-text">Evidence and verification</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                {closureChecklist.length > 0 && (
                  <span className={RUN_PILL_CLASS}>
                    {checklistCompleteCount}/{closureChecklist.length} checks complete
                  </span>
                )}
                <span className={RUN_PILL_CLASS}>
                  {evidencePointers.length} evidence pointer{evidencePointers.length === 1 ? '' : 's'}
                </span>
              </div>
            </div>

            <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
              <div className={runInsetClass('p-5')}>
                <h4 className="text-xs font-bold text-muted uppercase tracking-wider mb-4">Checklist</h4>
                {closureChecklist.length === 0 ? (
                  <p className="text-sm text-muted font-medium">Checklist items appear once the run has enough recorded state to verify closure.</p>
                ) : (
                  <div className="space-y-4">
                    {closureChecklist.map((item: RemediationClosureChecklistItem) => {
                      const linkedEvidence = item.evidence_keys
                        .map((evidenceKey) => evidenceByKey.get(evidenceKey))
                        .filter((pointer): pointer is RemediationEvidencePointer => Boolean(pointer));
                      return (
                        <div key={item.id} className={runControlClass('p-4')}>
                          <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                            <p className="text-sm font-bold text-text">{item.title}</p>
                            <Badge variant={getChecklistBadgeVariant(item.status)}>{getChecklistStatusLabel(item.status)}</Badge>
                          </div>
                          <p className="text-xs text-muted leading-relaxed">{item.detail}</p>
                          {linkedEvidence.length > 0 && (
                            <div className="mt-4 flex flex-wrap gap-2">
                              {linkedEvidence.map((pointer) => (
                                <Link
                                  key={`${item.id}-${pointer.key}`}
                                  href={withTenantQuery(
                                    resolveEvidenceNavigationHref(run.id, pointer.key, pointer.href, generatedFilesVisible),
                                    tenantId,
                                  )}
                                  className="text-xs font-bold text-accent hover:text-accent-hover flex items-center gap-1 transition-colors"
                                >
                                  {pointer.label}
                                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                  </svg>
                                </Link>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className={runInsetClass('p-5')}>
                <h4 className="text-xs font-bold text-muted uppercase tracking-wider mb-4">Evidence pointers</h4>
                {evidencePointers.length === 0 ? (
                  <p className="text-sm text-muted font-medium">No evidence pointers were recorded for this run.</p>
                ) : (
                  <div className="space-y-4">
                    {evidencePointers.map((pointer: RemediationEvidencePointer) => {
                      const evidenceHref = resolveRunSectionHref(pointer.href, generatedFilesVisible);
                      return (
                        <div key={pointer.key} id={getEvidenceCardId(pointer.key)} className={runControlClass('p-4')}>
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-sm font-bold text-text mb-1">{pointer.label}</p>
                              <p className="text-xs text-muted leading-relaxed">{pointer.description}</p>
                            </div>
                            <span className="rounded-full border border-[var(--border-soft)] bg-[var(--control-bg)] px-3 py-1 text-[11px] font-semibold text-muted">
                              {pointer.kind.replace(/_/g, ' ')}
                            </span>
                          </div>
                          {evidenceHref && (
                            <Link
                              href={withTenantQuery(evidenceHref, tenantId)}
                              className="mt-4 flex items-center gap-2 text-xs font-bold text-accent hover:text-accent-hover transition-colors"
                            >
                              Open evidence
                              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                              </svg>
                            </Link>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </section>

          <section id="run-technical-details" className={cn(runPanelClass(), 'p-6')}>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.24em] text-muted">{detailHeading}</p>
              <h3 className="mt-2 text-2xl font-semibold text-text">{detailHeading}</h3>
              <p className="mt-2 text-sm text-muted">Logs, progress signals, execution metadata, and generated files live here so they do not crowd the primary workflow.</p>
            </div>

            <div className="mt-5 space-y-3">
              <details className={cn('group p-4', RUN_INSET_CLASS)} open={!isTerminal}>
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">Progress and timing</p>
                    <p className="text-xs text-muted">Current phase, percentage, and the run timeline.</p>
                  </div>
                  <span className="text-accent group-open:rotate-90 transition-transform">▸</span>
                </summary>
                <div className="mt-4 space-y-5">
                  {isLoadingRun && (
                    <div>
                      <p className="text-xs font-bold text-muted uppercase tracking-wide mb-4">
                        {isBundleGeneration ? 'Generating PR bundle' : 'Processing remediation'}
                      </p>
                      <MultiStepLoader steps={loaderSteps} />
                    </div>
                  )}
                  <div className="flex items-center justify-between gap-4">
                    {steps.map((step, idx) => (
                      <div key={step.key} className="flex items-center flex-1 min-w-0">
                        <div className="flex flex-col items-center shrink-0">
                          <motion.div
                            initial={false}
                            animate={{
                              backgroundColor: step.done
                                ? (run.status === 'failed' || run.status === 'cancelled') && step.key === 'done'
                                  ? 'var(--color-danger)'
                                  : 'var(--color-accent)'
                                : 'var(--color-border)',
                              scale: run.status === step.key ? 1.1 : 1,
                            }}
                            className="w-8 h-8 rounded-full flex items-center justify-center border-2 border-border"
                          >
                            {step.done ? (
                              (run.status === 'failed' || run.status === 'cancelled') && step.key === 'done' ? (
                                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              ) : (
                                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                              )
                            ) : (
                              <span className="text-xs font-medium text-muted">{idx + 1}</span>
                            )}
                          </motion.div>
                          <span className="text-xs text-muted mt-1.5 truncate max-w-[80px]">{step.label}</span>
                        </div>
                        {idx < steps.length - 1 && (
                          <div className={`flex-1 h-0.5 mx-2 min-w-[16px] transition-colors ${step.done ? 'bg-accent' : 'bg-border'}`} />
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className={runControlClass('px-3 py-3 rounded-xl')}>
                      <p className="text-xs font-bold uppercase tracking-wide text-muted">Created</p>
                      <p className="mt-2 text-sm text-text">{createdAtLabel ?? 'Not recorded'}</p>
                    </div>
                    <div className={runControlClass('px-3 py-3 rounded-xl')}>
                      <p className="text-xs font-bold uppercase tracking-wide text-muted">Started</p>
                      <p className="mt-2 text-sm text-text">{startedAtLabel ?? 'Not started'}</p>
                    </div>
                    <div className={runControlClass('px-3 py-3 rounded-xl')}>
                      <p className="text-xs font-bold uppercase tracking-wide text-muted">Completed</p>
                      <p className="mt-2 text-sm text-text">{completedAtLabel ?? 'In progress'}</p>
                    </div>
                  </div>
                </div>
              </details>

              <details id="run-activity" className={cn('group p-4', RUN_INSET_CLASS)} open={run.status === 'failed' || run.status === 'cancelled'}>
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">Activity log</p>
                    <p className="text-xs text-muted">Backend log lines plus the current status message.</p>
                  </div>
                  <span className="text-accent group-open:rotate-90 transition-transform">▸</span>
                </summary>
                <div className={cn(runControlClass('mt-4 p-3 rounded-xl font-mono text-xs text-muted space-y-1 max-h-[420px] overflow-y-auto'), 'border-[var(--border-card)]')}>
                  {logLines.map((line, i) => (
                    <div key={i} className="flex gap-2">
                      <span className="text-accent/70 shrink-0">›</span>
                      <span className="break-words">{line}</span>
                    </div>
                  ))}
                </div>
              </details>

              {(executionError || execution || executionFolders.length > 0) && (
                <details className={cn('group p-4', RUN_INSET_CLASS)}>
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-text">Execution workspace</p>
                      <p className="text-xs text-muted">Worker execution metadata and per-folder command output.</p>
                    </div>
                    <span className="text-accent group-open:rotate-90 transition-transform">▸</span>
                  </summary>
                  <div className="mt-4 space-y-3">
                    {executionError && <p className="text-sm text-danger">{executionError}</p>}
                    {execution && (
                      <p className="text-sm text-muted">
                        Phase <span className="font-semibold text-text">{execution.phase}</span> · status <span className="font-semibold text-text">{execution.status}</span> · execution mode <span className="font-semibold text-text">{executionFailFast ? 'fail-fast' : 'continue-on-error'}</span>
                      </p>
                    )}
                    {!!executionFolders.length && (
                      <div className="space-y-2">
                        {executionFolders.map((folder, idx) => (
                          <div key={`${folder.folder}-${idx}`} className={runControlClass('rounded-xl p-3')}>
                            <div className="text-sm text-muted">
                              <span className="font-semibold text-text">{folder.folder}</span>: {folder.status}
                              {folder.error ? ` (${folder.error})` : ''}
                            </div>
                            {(folder.commands ?? []).map((command, commandIdx) => (
                              <details key={`${folder.folder}-command-${commandIdx}`} className="mt-3 rounded-lg border border-[var(--border-soft)] bg-[var(--card)] px-3 py-2">
                                <summary className="cursor-pointer text-xs text-text break-all">
                                  {command.command} (exit {command.returncode})
                                </summary>
                                <div className="mt-2 space-y-2">
                                  {command.stdout ? (
                                    <pre className="text-[11px] text-muted rounded p-2 whitespace-pre-wrap break-all border border-[var(--border-soft)] bg-[var(--control-bg)]">{command.stdout}</pre>
                                  ) : null}
                                  {command.stderr ? (
                                    <pre className="text-[11px] text-danger bg-danger/5 border border-danger/20 rounded p-2 whitespace-pre-wrap break-all">{command.stderr}</pre>
                                  ) : null}
                                </div>
                              </details>
                            ))}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </details>
              )}

              {generatedFilesVisible && (
                <details id="run-generated-files" className={cn('group p-4', RUN_INSET_CLASS)}>
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-text">Generated files</p>
                      <p className="text-xs text-muted">{prBundleFiles.length} Terraform file{prBundleFiles.length === 1 ? '' : 's'} ready for review.</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={downloadLoading}
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleDownloadBundle();
                        }}
                      >
                        {downloadLoading ? 'Downloading…' : 'Download bundle'}
                      </Button>
                      <span className="text-accent group-open:rotate-90 transition-transform">▸</span>
                    </div>
                  </summary>
                  <div className="mt-4 space-y-3">
                    {downloadError && <p className="text-sm text-danger" role="alert">{downloadError}</p>}
                    {prBundleFiles.map((file, index) => (
                      <div key={index} className={runControlClass('p-3 rounded-xl min-w-0')}>
                        <p className="text-xs font-mono text-muted mb-2 break-all">{file.path}</p>
                        <pre className="text-xs text-muted font-mono whitespace-pre-wrap break-all min-w-0">{file.content}</pre>
                      </div>
                    ))}
                  </div>
                </details>
              )}

              {run.status === 'success' && run.mode === 'pr_only' && (
                <details id="run-apply-guide" className={cn('group p-4', RUN_INSET_CLASS)}>
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-text">Apply guide</p>
                      <p className="text-xs text-muted">Detailed instructions for reviewing and shipping the generated Terraform.</p>
                    </div>
                    <span className="text-accent group-open:rotate-90 transition-transform">▸</span>
                  </summary>
                  <Tabs
                    containerClassName="mt-4"
                    contentClassName="text-sm text-muted rounded-xl border border-[var(--border-soft)] bg-[var(--card-inset)] p-3 break-words overflow-x-hidden"
                    tabs={prOnlyGuideTabs}
                  />
                </details>
              )}
            </div>
          </section>
        </div>
      </div>
    );
  }

  const actionCard = run.action ? (
    <div className={runInsetClass('p-5')}>
      <p className="text-sm font-bold uppercase tracking-tight text-muted mb-2">Action</p>
      <Link
        href={actionHref}
        className="text-accent hover:underline font-semibold"
      >
        {run.action.title}
      </Link>
      <p className="mt-2 inline-block rounded-lg border border-[var(--border-soft)] bg-[var(--control-bg)] px-2 py-1 text-xs font-mono text-muted">
        {run.action.account_id}
        {run.action.region && ` · ${run.action.region}`}
      </p>
      {run.action.status && (
        <p className="text-xs text-muted mt-2">
          Action status: <span className="font-semibold text-text">{run.action.status}</span>
        </p>
      )}
    </div>
  ) : null;

  const mainCard = (
    <div className={cn(runPanelClass(), 'overflow-hidden min-w-0')}>
      {pollError && (
        <div className="mx-6 mt-6 rounded-2xl border border-danger/20 bg-danger/10 p-4">
          <p className="text-sm font-medium text-danger">Run status may be stale</p>
          <p className="text-xs text-danger/80">{pollError}</p>
        </div>
      )}

      {/* Multi-step loader when run is pending/running (Generate PR flow) */}
      {isLoadingRun && (
        <div className="px-6 pt-6 pb-5 border-b border-border/30">
          <p className="text-xs font-bold text-muted uppercase tracking-wide mb-4">
            {isBundleGeneration ? 'Generating PR bundle' : 'Processing remediation'}
          </p>
          <MultiStepLoader steps={loaderSteps} />
        </div>
      )}
      {/* Percentage progress bar */}
      <div className="px-6 pt-6 pb-3">
        <div className="flex justify-between text-xs font-semibold text-muted mb-2">
          <span className="uppercase tracking-wide">{progressHeading}</span>
          <span>{progressPercent}%</span>
        </div>
        <div className={runControlClass('h-2.5 overflow-hidden p-0.5 rounded-full')}>
          <motion.div
            className="h-full rounded-full bg-tab-active shadow-[0_10px_22px_-14px_rgba(10,48,145,0.88)]"
            initial={{ width: 0 }}
            animate={{ width: `${progressPercent}%` }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
          />
        </div>
      </div>

      {/* Stale pending warning + Resend */}
      {isPendingStale && (
        <div className="mx-5 mb-4 p-3 bg-warning/10 border border-warning/30 rounded-xl space-y-2">
          <p className="text-sm text-warning font-medium">
            Run is still queued.
          </p>
          <p className="text-xs text-muted">
            If this persists, resend the job to retry processing.
          </p>
          {resendMessage && (
            <p className="text-xs text-accent">{resendMessage}</p>
          )}
          <Button
            variant="secondary"
            size="sm"
            onClick={async () => {
              setResendMessage(null);
              setResendLoading(true);
              try {
                await resendRemediationRun(runId, tenantId);
                setResendMessage('Job re-sent to queue. Worker should pick it up shortly.');
              } catch (err) {
                setResendMessage(getErrorMessage(err) || 'Failed to resend.');
              } finally {
                setResendLoading(false);
              }
            }}
            disabled={resendLoading}
          >
            {resendLoading ? 'Sending…' : 'Resend to queue'}
          </Button>
        </div>
      )}

      {/* Activity log (status + backend logs) */}
      <div id="run-activity" className="px-5 pb-4">
        <h4 className="text-xs font-medium text-muted uppercase tracking-wide mb-2">Activity</h4>
        <div className={cn(runControlClass('p-3 rounded-xl font-mono text-xs text-muted space-y-1 max-h-40 overflow-y-auto'), 'border-[var(--border-card)]')}>
          {logLines.map((line, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-accent/70 shrink-0">›</span>
              <span className="break-words">{line}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Status and outcome */}
      <div className="p-6 space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={getStatusBadgeVariant(run.status)}>
            {run.status}
          </Badge>
          {run.outcome && (
            <span className="text-sm text-text truncate">{run.outcome}</span>
          )}
          {generatedFilesVisible && (
            <Button
              variant="secondary"
              size="sm"
              disabled={downloadLoading}
              onClick={() => {
                void handleDownloadBundle();
              }}
            >
              {downloadLoading ? 'Downloading…' : 'Download bundle'}
            </Button>
          )}
          {canCancel && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancel}
              disabled={cancelLoading}
              className="text-muted hover:text-danger ml-auto"
            >
              {cancelLoading ? 'Cancelling…' : cancelLabel}
            </Button>
          )}
        </div>

        {run.started_at && (
          <p className="text-xs text-muted">
            Started: {new Date(run.started_at).toLocaleString()}
            {run.completed_at && (
              <> · Completed: {new Date(run.completed_at).toLocaleString()}</>
            )}
          </p>
        )}


        {showImplementationArtifacts && (
          <div className={cn('mt-6 p-5', RUN_INSET_CLASS)}>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <h4 className="text-xs font-bold text-muted uppercase tracking-wider">Implementation artifacts</h4>
              <span className={RUN_PILL_CLASS}>{implementationArtifacts.length} linked</span>
            </div>
            <div className="space-y-4">
              {implementationArtifacts.map((artifact) => {
                const metaSummary = getArtifactMetaSummary(artifact);
                const artifactHref = withTenantQuery(
                  resolveEvidenceNavigationHref(run.id, artifact.key, artifact.href, generatedFilesVisible),
                  tenantId,
                );
                return (
                  <div key={artifact.key} className={runControlClass('p-4')}>
                    <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-text mb-1">{artifact.label}</p>
                        <p className="text-xs text-muted leading-relaxed">{artifact.description}</p>
                      </div>
                      <Badge variant={artifact.executable ? 'success' : 'default'}>
                        {artifact.executable ? 'executable' : 'recorded'}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs font-medium text-muted mt-3">
                      <span className={RUN_PILL_CLASS}>
                        {artifact.kind.replace(/_/g, ' ')}
                      </span>
                      {metaSummary && (
                        <span className={RUN_PILL_CLASS}>
                          {metaSummary}
                        </span>
                      )}
                    </div>
                    {artifactHref && (
                      <Link
                        href={artifactHref}
                        className="mt-4 flex items-center gap-2 text-xs font-bold text-accent hover:text-accent-hover transition-colors"
                      >
                        Open artifact
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                        </svg>
                      </Link>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {!compact && (closureChecklist.length > 0 || evidencePointers.length > 0 || isTerminal) && (
          <div id="run-closure" className="mt-6 grid gap-5 xl:grid-cols-2">
            <div className={runInsetClass('p-5')}>
              <h4 className="text-xs font-bold text-muted uppercase tracking-wider mb-4">Closure checklist</h4>
              {closureChecklist.length === 0 ? (
                <p className="text-sm text-muted font-medium">Checklist will populate when the run reaches a terminal state.</p>
              ) : (
                <div className="space-y-4">
                  {closureChecklist.map((item: RemediationClosureChecklistItem) => {
                    const linkedEvidence = item.evidence_keys
                      .map((evidenceKey) => evidenceByKey.get(evidenceKey))
                      .filter((pointer): pointer is RemediationEvidencePointer => Boolean(pointer));
                    return (
                      <div key={item.id} className={runControlClass('p-4')}>
                        <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                          <p className="text-sm font-bold text-text">{item.title}</p>
                          <Badge variant={getChecklistBadgeVariant(item.status)}>
                            {getChecklistStatusLabel(item.status)}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted leading-relaxed">{item.detail}</p>
                        {linkedEvidence.length > 0 && (
                          <div className="mt-4 flex flex-wrap gap-2">
                            {linkedEvidence.map((pointer) => (
                              <Link
                                key={`${item.id}-${pointer.key}`}
                                href={withTenantQuery(
                                  resolveEvidenceNavigationHref(run.id, pointer.key, pointer.href, generatedFilesVisible),
                                  tenantId,
                                )}
                                className="text-xs font-bold text-accent hover:text-accent-hover flex items-center gap-1 transition-colors"
                              >
                                {pointer.label}
                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                </svg>
                              </Link>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className={runInsetClass('p-5')}>
              <h4 className="text-xs font-bold text-muted uppercase tracking-wider mb-4">Evidence pointers</h4>
              {evidencePointers.length === 0 ? (
                <p className="text-sm text-muted font-medium">No evidence pointers recorded yet.</p>
              ) : (
                <div className="space-y-4">
                  {evidencePointers.map((pointer: RemediationEvidencePointer) => {
                    const evidenceHref = resolveRunSectionHref(pointer.href, generatedFilesVisible);
                    return (
                      <div
                        key={pointer.key}
                        id={getEvidenceCardId(pointer.key)}
                        className={runControlClass('p-4')}
                      >
                        <p className="text-sm font-bold text-text mb-1">{pointer.label}</p>
                        <p className="text-xs text-muted leading-relaxed">{pointer.description}</p>
                        <div className="mt-4 flex flex-wrap gap-2 text-xs font-medium text-muted">
                          <span className={RUN_PILL_CLASS}>
                            {pointer.kind.replace(/_/g, ' ')}
                          </span>
                        </div>
                        {evidenceHref && (
                          <Link
                            href={withTenantQuery(evidenceHref, tenantId)}
                            className="mt-4 flex items-center gap-2 text-xs font-bold text-accent hover:text-accent-hover transition-colors"
                          >
                            Open evidence
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                            </svg>
                          </Link>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* PR bundle files (when successful and pr_only) — Step 9.6 */}
        {generatedFilesVisible && (
          <details id="run-generated-files" className="mt-4 group">
            <summary className={cn('mb-2 flex cursor-pointer list-none items-center justify-between gap-4 rounded-xl p-4', RUN_INSET_CLASS)}>
              <div className="flex items-center gap-2">
                <span className="text-accent group-open:rotate-90 transition-transform">▸</span>
                <h4 className="text-xs font-medium text-muted uppercase tracking-wide">Generated files</h4>
              </div>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={downloadLoading}
                onClick={async (e) => {
                  e.stopPropagation();
                  const prBundle = (run.artifacts as { pr_bundle: { files: { path: string; content: string }[] } }).pr_bundle;
                  if (!prBundle?.files?.length) return;
                  setDownloadError(null);
                  setDownloadLoading(true);
                  try {
                    await downloadPrBundleZip(run.id, prBundle.files);
                  } catch (err) {
                    setDownloadError(getErrorMessage(err));
                  } finally {
                    setDownloadLoading(false);
                  }
                }}
              >
                {downloadLoading ? 'Downloading…' : 'Download bundle'}
              </Button>
            </summary>
            <div className={cn('mt-2 min-w-0 space-y-3 rounded-xl p-4', RUN_INSET_CLASS)}>
              {downloadError && (
                <p className="text-xs text-red-500 mb-2" role="alert">
                  {downloadError}
                </p>
              )}
              <div className="space-y-3 min-w-0">
                {((run.artifacts as { pr_bundle: { files: { path: string; content: string }[] } }).pr_bundle.files).map((f: { path: string; content: string }, i: number) => (
                  <div key={i} className={runControlClass('p-3 rounded-xl min-w-0')}>
                    <p className="text-xs font-mono text-muted mb-2 break-all">{f.path}</p>
                    <pre className="text-xs text-muted font-mono whitespace-pre-wrap break-all min-w-0">
                      {f.content}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          </details>
        )}

        {/* Next steps (Step 9.7): when run succeeds, guide user to review, apply, verify */}
        {run.status === 'success' && !compact && (
          <div className="mt-4 p-4 bg-accent/10 border border-accent/20 rounded-xl">
            <h4 className="text-sm font-medium text-text mb-2">Next steps</h4>
            {run.mode === 'pr_only' ? (
              <ol className="text-sm text-muted space-y-3 list-decimal list-inside">
                <li>
                  <strong className="text-text">Review and download the generated files.</strong> Use the &quot;Download bundle&quot; button on this page (or in your pipeline) to get a zip of the IaC files (Terraform <code className="text-xs">.tf</code>). Open the files locally and review resources, variables, and target IDs (e.g. bucket name, security group ID) to ensure they match your environment before applying.
                </li>
                <li>
                  <strong className="text-text">Apply the changes in AWS.</strong>
                  <Tabs
                    containerClassName="mt-2"
                    contentClassName="text-sm text-muted rounded-xl border border-[var(--border-soft)] bg-[var(--card-inset)] p-3 break-words overflow-x-hidden"
                    tabs={[
                      {
                        title: 'Pipeline (Terraform)',
                        value: 'pipeline-terraform',
                        content: (
                          <div className="space-y-2">
                            <p><strong className="text-text">Terraform</strong> is a tool that creates or updates cloud resources from <code className="text-xs">.tf</code> files. If this is your first time, follow these steps.</p>
                            <ol className="list-decimal list-inside space-y-1.5 ml-1">
                              <li>Download the bundle (above) and unzip it. You should see <code className="text-xs">.tf</code> files (e.g. <code className="text-xs">main.tf</code>, <code className="text-xs">providers.tf</code>).</li>
                              <li>Install Terraform on the machine that runs your pipeline (e.g. <a href="https://developer.hashicorp.com/terraform/install" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">install guide</a>).</li>
                              <li>Put the unzipped files into your infrastructure Git repo — e.g. create a new branch, add the files, commit and push.</li>
                              <li>In your CI/CD pipeline (GitHub Actions, GitLab CI, AWS CodePipeline, etc.), configure the job to use the <strong className="text-text">same AWS account and region</strong> as this action (set credentials and <code className="text-xs">AWS_REGION</code> or <code className="text-xs">TF_VAR_region</code>).</li>
                              <li>In the pipeline, run in order: <code className="text-xs">terraform init</code> (downloads providers), <code className="text-xs">terraform plan</code> (shows what will change), then <code className="text-xs">terraform apply -auto-approve</code> (applies changes). Optionally add a manual approval step between plan and apply.</li>
                              <li>Trigger the pipeline (push or merge) so it runs in that account and region.</li>
                            </ol>
                          </div>
                        ),
                      },
                      {
                        title: 'Merge PR',
                        value: 'merge-pr',
                        content: (
                          <div className="space-y-2">
                            <p><strong className="text-text">A Pull Request (PR)</strong> — or Merge Request (MR) — lets you propose changes for review before they go into your main branch. If this is your first time, follow these steps.</p>
                            <ol className="list-decimal list-inside space-y-1.5 ml-1">
                              <li>Download the bundle (above) and unzip it. Create a new branch in your infrastructure repo (e.g. <code className="text-xs">git checkout -b fix-remediation</code>).</li>
                              <li>Copy the unzipped files into the repo folder, then run <code className="text-xs">git add .</code> and <code className="text-xs">git commit -m &quot;Apply remediation from AWS Security Autopilot&quot;</code>.</li>
                              <li>Push the branch (e.g. <code className="text-xs">git push -u origin fix-remediation</code>).</li>
                              <li>In GitHub, GitLab, or Bitbucket, open a new Pull Request / Merge Request from this branch to your main (or default) branch. In the description, note that this applies the remediation for this action.</li>
                              <li>After someone reviews and approves, merge the PR. The branch you merge into should already have a pipeline that runs Terraform (see the Pipeline tab). If you don’t have a pipeline yet, set one up using the &quot;Pipeline (Terraform)&quot; tab, then merge this PR so the pipeline runs.</li>
                              <li>Ensure the pipeline uses the <strong className="text-text">same AWS account and region</strong> as this action.</li>
                            </ol>
                          </div>
                        ),
                      },
                    ]}
                  />
                </li>
                <li>
                  <strong className="text-text">Verify the finding is resolved.</strong>{' '}
                  <Link
                    href={actionHref}
                    className="text-accent hover:underline"
                  >
                    Return to the action
                  </Link>
                  {' '}and click <strong>Recompute actions</strong> (or trigger a fresh ingest). This refreshes action status so you can confirm the finding is no longer open.
                </li>
              </ol>
            ) : (
              <p className="text-sm text-muted">
                Fix applied. Click{' '}
                <Link
                  href={actionHref}
                  className="text-accent hover:underline"
                >
                  Recompute actions
                </Link>
                {' '}on the action detail page to confirm this finding is resolved.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );

  if (fullWidth) {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)] gap-6 items-start">
        <div className="min-w-0 space-y-4">
          {actionCard}
        </div>
        <div className="min-w-0">{mainCard}</div>
      </div>
    );
  }

  return (
    <div className="space-y-4 min-w-0">
      {actionCard}
      {mainCard}
    </div>
  );
}
