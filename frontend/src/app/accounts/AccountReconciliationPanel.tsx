'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  REMEDIATION_EYEBROW_CLASS,
  RemediationCallout,
  RemediationPanel,
  remediationInsetClass,
} from '@/components/ui/remediation-surface';
import { cn } from '@/lib/utils';
import {
  AwsAccount,
  getErrorMessage,
  getReconciliationCoverage,
  getReconciliationSettings,
  getReconciliationStatus,
  preflightReconciliation,
  ReconciliationCoverageResponse,
  ReconciliationPreflightResponse,
  ReconciliationStatusResponse,
  runReconciliation,
  updateReconciliationSettings,
} from '@/lib/api';
import { formatUtcDateTime } from './date-format';

const DEFAULT_SERVICES = ['ec2', 's3', 'cloudtrail', 'config', 'iam', 'ebs', 'rds', 'eks', 'ssm', 'guardduty'];
const DASHBOARD_SELECT_CLASS =
  'w-full rounded-[1.2rem] border border-border/55 bg-[rgba(235,242,255,0.58)] px-3 py-2 text-sm text-text shadow-[inset_0_1px_0_rgba(235,242,255,0.45)] outline-none transition focus:ring-2 focus:ring-ring dark:bg-[#050812]/86 dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]';

function csvToList(value: string): string[] {
  return value
    .split(',')
    .map((v) => v.trim().toLowerCase())
    .filter(Boolean);
}

function runStatusVariant(status: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  const value = (status || '').toLowerCase();
  if (value === 'succeeded') return 'success';
  if (value === 'failed') return 'danger';
  if (value === 'partial_failed') return 'warning';
  if (value === 'running') return 'info';
  if (value === 'queued') return 'warning';
  return 'default';
}

interface AccountReconciliationPanelProps {
  account: AwsAccount;
  tenantId?: string;
  onUpdate?: () => void;
}

export function AccountReconciliationPanel({
  account,
  tenantId,
  onUpdate,
}: AccountReconciliationPanelProps) {
  const [servicesCsv, setServicesCsv] = useState(DEFAULT_SERVICES.join(','));
  const [regionsCsv, setRegionsCsv] = useState((account.regions || []).join(','));
  const [maxResources, setMaxResources] = useState(500);
  const [sweepMode, setSweepMode] = useState<'global' | 'targeted'>('global');
  const [requirePreflightPass, setRequirePreflightPass] = useState(true);
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [scheduleIntervalMinutes, setScheduleIntervalMinutes] = useState(360);
  const [scheduleCooldownMinutes, setScheduleCooldownMinutes] = useState(30);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [preflighting, setPreflighting] = useState(false);
  const [statusData, setStatusData] = useState<ReconciliationStatusResponse | null>(null);
  const [coverageData, setCoverageData] = useState<ReconciliationCoverageResponse | null>(null);
  const [preflightData, setPreflightData] = useState<ReconciliationPreflightResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const services = useMemo(() => csvToList(servicesCsv), [servicesCsv]);
  const regions = useMemo(() => csvToList(regionsCsv), [regionsCsv]);
  const accountValidated = account.status.toLowerCase() === 'validated';

  const loadPanelData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusResponse, coverageResponse, settingsResponse] = await Promise.all([
        getReconciliationStatus({ account_id: account.account_id, limit: 20 }, tenantId),
        getReconciliationCoverage({ account_id: account.account_id }, tenantId),
        getReconciliationSettings(account.account_id, tenantId),
      ]);
      setStatusData(statusResponse);
      setCoverageData(coverageResponse);
      setScheduleEnabled(Boolean(settingsResponse.enabled));
      setScheduleIntervalMinutes(Number(settingsResponse.interval_minutes || 360));
      setScheduleCooldownMinutes(Number(settingsResponse.cooldown_minutes || 30));
      setMaxResources(Number(settingsResponse.max_resources || 500));
      setSweepMode((settingsResponse.sweep_mode || 'global') === 'targeted' ? 'targeted' : 'global');
      setServicesCsv((settingsResponse.services || DEFAULT_SERVICES).join(','));
      setRegionsCsv((settingsResponse.regions || account.regions || []).join(','));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [account.account_id, account.regions, tenantId]);

  useEffect(() => {
    loadPanelData().catch(() => undefined);
  }, [loadPanelData]);

  async function handlePreflight() {
    setError(null);
    setMessage(null);
    setPreflighting(true);
    try {
      const result = await preflightReconciliation(
        {
          account_id: account.account_id,
          services,
          regions,
        },
        tenantId,
      );
      setPreflightData(result);
      if (result.ok) {
        setMessage('Preflight passed.');
      } else {
        setError('Preflight failed. Check missing permissions before running reconciliation.');
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setPreflighting(false);
    }
  }

  async function handleRunNow() {
    setError(null);
    setMessage(null);
    setRunning(true);
    try {
      const result = await runReconciliation(
        {
          account_id: account.account_id,
          services,
          regions,
          max_resources: maxResources,
          sweep_mode: sweepMode,
          require_preflight_pass: requirePreflightPass,
        },
        tenantId,
      );
      if (result.preflight) {
        setPreflightData(result.preflight);
      }
      setMessage(`Run queued (${result.enqueued_shards}/${result.total_shards} shards).`);
      await loadPanelData();
      onUpdate?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setRunning(false);
    }
  }

  async function handleSaveSchedule() {
    setError(null);
    setMessage(null);
    setSavingSchedule(true);
    try {
      await updateReconciliationSettings(
        account.account_id,
        {
          enabled: scheduleEnabled,
          interval_minutes: scheduleIntervalMinutes,
          cooldown_minutes: scheduleCooldownMinutes,
          services,
          regions,
          max_resources: maxResources,
          sweep_mode: sweepMode,
        },
        tenantId,
      );
      setMessage('Schedule settings saved.');
      await loadPanelData();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSavingSchedule(false);
    }
  }

  return (
    <RemediationPanel className="p-6">
      <div className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className={REMEDIATION_EYEBROW_CLASS}>Reconciliation</p>
            <h3 className="mt-3 text-lg font-semibold text-text">Inventory reconciliation, preflight checks, and schedule controls</h3>
            <p className="mt-2 max-w-3xl text-sm leading-7 text-text/72">
              Use reconciliation to rescan inventory coverage, inspect failure reasons, and keep scheduled sweeps aligned with each account’s regions and service scope.
            </p>
          </div>
          {loading ? <Badge variant="info">Loading</Badge> : null}
        </div>

        {!accountValidated ? (
          <RemediationCallout
            tone="warning"
            title="Validation required"
            description={`Account status is ${account.status}. Revalidate the ReadRole before running reconciliation.`}
          />
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
          <div className={remediationInsetClass('default', 'space-y-4 p-5')}>
            <div>
              <p className={REMEDIATION_EYEBROW_CLASS}>Run configuration</p>
              <p className="mt-3 text-sm leading-6 text-text/72">
                Tune the reconciliation sweep before you launch a run. Use CSV lists to scope services or regions explicitly.
              </p>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <Input
                label="Services (CSV)"
                value={servicesCsv}
                onChange={(event) => setServicesCsv(event.target.value)}
                placeholder="ec2,s3,cloudtrail"
              />
              <Input
                label="Regions (CSV)"
                value={regionsCsv}
                onChange={(event) => setRegionsCsv(event.target.value)}
                placeholder="us-east-1,eu-north-1"
              />
              <Input
                label="Max resources per shard"
                type="number"
                min={1}
                max={5000}
                value={String(maxResources)}
                onChange={(event) => setMaxResources(Number(event.target.value) || 500)}
              />
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-text">Sweep mode</label>
                <select
                  className={DASHBOARD_SELECT_CLASS}
                  value={sweepMode}
                  onChange={(event) => setSweepMode(event.target.value === 'targeted' ? 'targeted' : 'global')}
                >
                  <option value="global">Global</option>
                  <option value="targeted">Targeted</option>
                </select>
              </div>
            </div>

            <label className="inline-flex items-center gap-2 text-sm text-text/72">
              <input
                type="checkbox"
                checked={requirePreflightPass}
                onChange={(event) => setRequirePreflightPass(event.target.checked)}
              />
              Block runs if preflight fails
            </label>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={handlePreflight}
                isLoading={preflighting}
                disabled={!accountValidated}
              >
                Run preflight
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleRunNow}
                isLoading={running}
                disabled={!accountValidated}
              >
                Run now
              </Button>
            </div>
          </div>

          <div className="space-y-4">
            {preflightData ? (
              <RemediationCallout
                tone={preflightData.ok ? 'success' : 'danger'}
                title={`Preflight ${preflightData.ok ? 'passed' : 'failed'} (${preflightData.region_used})`}
                description={
                  !preflightData.ok && preflightData.missing_permissions.length > 0
                    ? `Missing permissions: ${preflightData.missing_permissions.join(', ')}`
                    : undefined
                }
              >
                {preflightData.warnings.length > 0 ? (
                  <p className="text-sm text-text/74">Warnings: {preflightData.warnings.join(' | ')}</p>
                ) : null}
              </RemediationCallout>
            ) : null}

            {statusData?.summary.alerts?.length ? (
              <RemediationCallout tone="warning" title="Open reconciliation alerts">
                <div className="space-y-1 text-sm text-text/76">
                  {statusData.summary.alerts.map((alert) => (
                    <p key={alert.code}>{alert.detail} ({alert.count})</p>
                  ))}
                </div>
              </RemediationCallout>
            ) : null}

            {coverageData ? (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className={remediationInsetClass('default', 'p-4')}>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Coverage</p>
                  <p className="mt-3 text-2xl font-semibold text-text">{(coverageData.coverage_rate * 100).toFixed(1)}%</p>
                </div>
                <div className={remediationInsetClass('default', 'p-4')}>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Matched</p>
                  <p className="mt-3 text-2xl font-semibold text-text">{coverageData.in_scope_matched}</p>
                </div>
                <div className={remediationInsetClass('default', 'p-4')}>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Unmatched</p>
                  <p className="mt-3 text-2xl font-semibold text-text">{coverageData.in_scope_unmatched}</p>
                </div>
                <div className={remediationInsetClass('default', 'p-4')}>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Lag since success</p>
                  <p className="mt-3 text-2xl font-semibold text-text">
                    {statusData?.summary.lag_since_last_success_minutes != null
                      ? `${statusData.summary.lag_since_last_success_minutes.toFixed(1)}m`
                      : '—'}
                  </p>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        {statusData ? (
          <div className={remediationInsetClass('default', 'space-y-4 p-5')}>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge variant="warning">Queued {statusData.summary.queued_runs}</Badge>
              <Badge variant="info">Running {statusData.summary.running_runs}</Badge>
              <Badge variant="success">Succeeded {statusData.summary.succeeded_runs}</Badge>
              <Badge variant="warning">Partial {statusData.summary.partial_failed_runs}</Badge>
              <Badge variant="danger">Failed {statusData.summary.failed_runs}</Badge>
              <span className="ml-2 text-text/68">Success rate {(statusData.summary.success_rate * 100).toFixed(1)}%</span>
            </div>

            <div className="space-y-2">
              {statusData.runs.slice(0, 5).map((run) => (
                <div
                  key={run.id}
                  className={cn(
                    remediationInsetClass('default', 'flex flex-wrap items-center justify-between gap-3 p-4'),
                    'border-border/45',
                  )}
                >
                  <div className="space-y-1">
                    <p className="text-xs text-text/62">
                      {formatUtcDateTime(run.submitted_at)} • {run.services.join(', ')}
                    </p>
                    <p className="text-sm text-text">
                      {run.succeeded_shards}/{run.total_shards} succeeded
                      {run.failed_shards > 0 ? ` • ${run.failed_shards} failed` : ''}
                    </p>
                  </div>
                  <Badge variant={runStatusVariant(run.status)}>{run.status}</Badge>
                </div>
              ))}
              {statusData.runs.length === 0 ? (
                <p className="text-sm text-text/68">No reconciliation runs have been recorded for this account yet.</p>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className={remediationInsetClass('default', 'space-y-4 p-5')}>
          <div>
            <p className={REMEDIATION_EYEBROW_CLASS}>Schedule</p>
            <p className="mt-3 text-sm leading-6 text-text/72">
              Configure recurring reconciliation to keep coverage current even when no operator manually triggers a run.
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <label className="inline-flex items-center gap-2 text-sm text-text/72 md:mt-7">
              <input
                type="checkbox"
                checked={scheduleEnabled}
                onChange={(event) => setScheduleEnabled(event.target.checked)}
              />
              Enabled
            </label>
            <Input
              label="Interval (minutes)"
              type="number"
              min={1}
              max={10080}
              value={String(scheduleIntervalMinutes)}
              onChange={(event) => setScheduleIntervalMinutes(Number(event.target.value) || 360)}
            />
            <Input
              label="Cooldown (minutes)"
              type="number"
              min={1}
              max={1440}
              value={String(scheduleCooldownMinutes)}
              onChange={(event) => setScheduleCooldownMinutes(Number(event.target.value) || 30)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="secondary" size="sm" onClick={handleSaveSchedule} isLoading={savingSchedule}>
              Save schedule
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { void loadPanelData(); }}
              disabled={loading}
            >
              Refresh status
            </Button>
          </div>
        </div>

        {message ? <RemediationCallout tone="success" description={message} /> : null}
        {error ? <RemediationCallout tone="danger" description={error} /> : null}
      </div>
    </RemediationPanel>
  );
}
