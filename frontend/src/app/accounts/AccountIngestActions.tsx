'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { SelectDropdown } from '@/components/ui/SelectDropdown';
import { RemediationCallout, remediationInsetClass, REMEDIATION_EYEBROW_CLASS } from '@/components/ui/remediation-surface';
import {
  AwsAccount,
  triggerIngest,
  triggerIngestAccessAnalyzer,
  triggerIngestInspector,
  getIngestProgress,
  getErrorMessage,
  IngestResponse,
} from '@/lib/api';
import { useBackgroundJobs } from '@/contexts/BackgroundJobsContext';
import {
  SOURCE_SECURITY_HUB,
  SOURCE_ACCESS_ANALYZER,
  SOURCE_INSPECTOR,
  getSourceLabel,
} from '@/lib/source';

export type IngestSource = typeof SOURCE_SECURITY_HUB | typeof SOURCE_ACCESS_ANALYZER | typeof SOURCE_INSPECTOR;

const INGEST_SOURCES: { value: IngestSource; label: string }[] = [
  { value: SOURCE_SECURITY_HUB, label: getSourceLabel(SOURCE_SECURITY_HUB) },
  { value: SOURCE_ACCESS_ANALYZER, label: getSourceLabel(SOURCE_ACCESS_ANALYZER) },
  { value: SOURCE_INSPECTOR, label: getSourceLabel(SOURCE_INSPECTOR) },
];

interface AccountIngestActionsProps {
  account: AwsAccount;
  tenantId?: string;
  onUpdate?: () => void;
  /** Compact layout (e.g. table row): single line, minimal copy. */
  compact?: boolean;
  /** Modal layout: prominent Refresh (primary) + data source row, neat organization. */
  layout?: 'inline' | 'modal';
}

function triggerBySource(
  accountId: string,
  source: IngestSource,
  tenantId?: string,
  regions?: string[]
): Promise<IngestResponse> {
  switch (source) {
    case SOURCE_SECURITY_HUB:
      return triggerIngest(accountId, tenantId, regions);
    case SOURCE_ACCESS_ANALYZER:
      return triggerIngestAccessAnalyzer(accountId, tenantId, regions);
    case SOURCE_INSPECTOR:
      return triggerIngestInspector(accountId, tenantId, regions);
    default:
      return triggerIngest(accountId, tenantId, regions);
  }
}

export function AccountIngestActions({
  account,
  tenantId,
  onUpdate,
  compact = false,
  layout = 'inline',
}: AccountIngestActionsProps) {
  const [selectedSource, setSelectedSource] = useState<IngestSource>(SOURCE_SECURITY_HUB);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isIngestingAll, setIsIngestingAll] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const { addJob, updateJob, completeJob, failJob, timeoutJob } = useBackgroundJobs();

  const canIngest = account.status === 'validated';
  const isBusy = isIngesting || isIngestingAll;
  const messageTone = message?.type === 'success' ? 'success' : 'danger';

  const monitorIngestProgress = async (
    jobId: string,
    startedAfter: string,
    source?: IngestSource
  ) => {
    const attempts = 18; // ~3 minutes at 10s interval
    for (let i = 0; i < attempts; i += 1) {
      if (i > 0) {
        await new Promise((resolve) => setTimeout(resolve, 10_000));
      }
      try {
        const progress = await getIngestProgress(
          account.account_id,
          {
            started_after: startedAfter,
            source,
          },
          tenantId
        );
        if (progress.status === 'completed') {
          completeJob(
            jobId,
            'Refresh completed.',
            `Updated findings: ${progress.updated_findings_count}`
          );
          return;
        }
        if (progress.status === 'no_changes_detected') {
          completeJob(
            jobId,
            'Refresh completed (no changes detected).',
            'Worker completed but no finding updates were detected for this window.'
          );
          return;
        }
        updateJob(jobId, {
          status: progress.status === 'queued' ? 'queued' : 'running',
          progress: progress.progress,
          message: progress.message,
          detail: `Elapsed ${progress.elapsed_seconds}s`,
        });
      } catch (err) {
        updateJob(jobId, {
          status: 'running',
          progress: Math.min(90, 30 + i * 3),
          detail: `Progress check retrying: ${getErrorMessage(err)}`,
        });
      }
    }
    timeoutJob(
      jobId,
      'Refresh is taking longer than expected.',
      'Worker may still be processing. You can refresh Findings in a minute.'
    );
  };

  const handleRefreshOne = async () => {
    if (!canIngest || isBusy) return;
    setIsIngesting(true);
    setMessage(null);
    const startedAfter = new Date().toISOString();
    const jobId = addJob({
      type: 'findings',
      title: `Refreshing ${getSourceLabel(selectedSource)} (${account.account_id})`,
      message: 'Queuing refresh request…',
      progress: 8,
      dedupeKey: `refresh-source:${account.account_id}:${selectedSource}`,
      resourceId: account.account_id,
    });
    try {
      const response = await triggerBySource(
        account.account_id,
        selectedSource,
        tenantId,
        account.regions?.length ? account.regions : undefined
      );
      updateJob(jobId, {
        status: 'queued',
        progress: 15,
        message: 'Refresh request queued. Waiting for worker processing…',
      });
      void monitorIngestProgress(jobId, startedAfter, selectedSource);
      setMessage({
        type: 'success',
        text: `${getSourceLabel(selectedSource)} refresh started (${response.jobs_queued} region(s) queued). Live progress is now visible in the notification center.`,
      });
      onUpdate?.();
    } catch (err) {
      failJob(jobId, 'Refresh failed.', getErrorMessage(err));
      setMessage({ type: 'error', text: getErrorMessage(err) });
    } finally {
      setIsIngesting(false);
    }
  };

  const handleRefreshAll = async () => {
    if (!canIngest || isBusy) return;
    setIsIngestingAll(true);
    setMessage(null);
    const startedAfter = new Date().toISOString();
    const jobId = addJob({
      type: 'findings',
      title: `Refreshing all sources (${account.account_id})`,
      message: 'Queuing refresh request…',
      progress: 8,
      dedupeKey: `refresh-all:${account.account_id}`,
      resourceId: account.account_id,
    });
    try {
      const [hubRes, aaRes, inspRes] = await Promise.all([
        triggerIngest(account.account_id, tenantId, account.regions?.length ? account.regions : undefined),
        triggerIngestAccessAnalyzer(account.account_id, tenantId, account.regions?.length ? account.regions : undefined),
        triggerIngestInspector(account.account_id, tenantId, account.regions?.length ? account.regions : undefined),
      ]);
      updateJob(jobId, {
        status: 'queued',
        progress: 15,
        message: 'All refresh requests queued. Waiting for worker processing…',
      });
      void monitorIngestProgress(jobId, startedAfter);
      const parts: string[] = [];
      if (hubRes.jobs_queued) parts.push(`Security Hub: ${hubRes.jobs_queued} region(s)`);
      if (aaRes.jobs_queued) parts.push(`Access Analyzer: ${aaRes.jobs_queued} region(s)`);
      if (inspRes.jobs_queued) parts.push(`Inspector: ${inspRes.jobs_queued} region(s)`);
      setMessage({
        type: 'success',
        text: parts.length
          ? `All findings refresh started (${parts.join(', ')}). Live progress is now visible in the notification center.`
          : 'All findings refresh started. Live progress is now visible in the notification center.',
      });
      onUpdate?.();
    } catch (err) {
      failJob(jobId, 'Refresh failed.', getErrorMessage(err));
      setMessage({ type: 'error', text: getErrorMessage(err) });
    } finally {
      setIsIngestingAll(false);
    }
  };

  if (layout === 'modal') {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
          <div className={remediationInsetClass('default', 'space-y-2')}>
            <p className={REMEDIATION_EYEBROW_CLASS}>Data source</p>
            <p className="text-sm leading-6 text-text/74">
              Choose a source for a targeted refresh or queue all sources for a full account data pass.
            </p>
            <SelectDropdown<IngestSource>
              value={selectedSource}
              onValueChange={setSelectedSource}
              options={INGEST_SOURCES}
              disabled={isBusy || !canIngest}
              aria-label="Finding source to refresh"
              triggerClassName="min-w-0"
            />
          </div>

          <div className={remediationInsetClass('accent', 'flex flex-wrap items-center gap-3')}>
            <Button
              variant="primary"
              size="sm"
              onClick={handleRefreshOne}
              isLoading={isIngesting}
              disabled={isIngestingAll || !canIngest}
              className="rounded-xl"
            >
              {isIngesting ? 'Queuing...' : 'Refresh findings'}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRefreshAll}
              isLoading={isIngestingAll}
              disabled={isIngesting || !canIngest}
              className="rounded-xl"
            >
              {isIngestingAll ? 'Queuing...' : 'Refresh all sources'}
            </Button>
            <p className="text-sm text-text/70">
              {canIngest
                ? 'Queued jobs will appear immediately in the notification center.'
                : 'Refresh is disabled until the account returns to validated status.'}
            </p>
          </div>
        </div>
        {message ? (
          <RemediationCallout tone={messageTone}>
            <p className="text-sm">{message.text}</p>
          </RemediationCallout>
        ) : null}
      </div>
    );
  }

  if (compact) {
    return (
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2 flex-nowrap">
          <SelectDropdown<IngestSource>
            value={selectedSource}
            onValueChange={setSelectedSource}
            options={INGEST_SOURCES}
            disabled={isBusy || !canIngest}
            aria-label="Finding source to refresh"
            triggerClassName="min-w-0"
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefreshOne}
            isLoading={isIngesting}
            disabled={isIngestingAll || !canIngest}
          >
            {isIngesting ? 'Queuing...' : 'Refresh'}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleRefreshAll}
            isLoading={isIngestingAll}
            disabled={isIngesting || !canIngest}
          >
            {isIngestingAll ? 'Queuing...' : 'All sources'}
          </Button>
        </div>
        {message && (
          <span className={`text-xs ${message.type === 'success' ? 'text-success' : 'text-danger'}`}>
            {message.text}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-sm text-muted shrink-0">Data source</label>
        <SelectDropdown<IngestSource>
          value={selectedSource}
          onValueChange={setSelectedSource}
          options={INGEST_SOURCES}
          disabled={isBusy || !canIngest}
          aria-label="Finding source to refresh"
          triggerClassName="min-w-0"
        />
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefreshOne}
          isLoading={isIngesting}
          disabled={isIngestingAll || !canIngest}
        >
          {isIngesting ? 'Queuing...' : 'Refresh findings'}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleRefreshAll}
          isLoading={isIngestingAll}
          disabled={isIngesting || !canIngest}
        >
          {isIngestingAll ? 'Queuing...' : 'Refresh all sources'}
        </Button>
      </div>
      {message && (
        <RemediationCallout tone={messageTone}>
          <p className="text-sm">{message.text}</p>
        </RemediationCallout>
      )}
    </div>
  );
}
