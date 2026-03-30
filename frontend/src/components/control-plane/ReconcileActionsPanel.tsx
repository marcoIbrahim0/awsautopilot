'use client';

import { useMemo, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  enqueueReconcileInventoryGlobal,
  enqueueReconcileInventoryShard,
  enqueueReconcileRecentlyTouched,
  getErrorMessage,
} from '@/lib/api';

interface ReconcileActionsPanelProps {
  tenantId: string;
  defaultServices: string[];
  defaultMaxResources: number;
  onSubmitted: () => Promise<void> | void;
}

function csvToList(value: string): string[] {
  return value
    .split(',')
    .map((v) => v.trim().toLowerCase())
    .filter(Boolean);
}

export function ReconcileActionsPanel({
  tenantId,
  defaultServices,
  defaultMaxResources,
  onSubmitted,
}: ReconcileActionsPanelProps) {
  const rawFlag = process.env.NEXT_PUBLIC_CONTROL_PLANE_RECONCILE_UI_ENABLED;
  const featureEnabled = (rawFlag ?? '').toLowerCase() === 'true' || rawFlag === '1';

  const [lookbackMinutes, setLookbackMinutes] = useState(60);
  const [servicesCsv, setServicesCsv] = useState(defaultServices.join(','));
  const [maxResources, setMaxResources] = useState(defaultMaxResources);

  const [globalAccountsCsv, setGlobalAccountsCsv] = useState('');
  const [globalRegionsCsv, setGlobalRegionsCsv] = useState('');

  const [shardAccountId, setShardAccountId] = useState('');
  const [shardRegion, setShardRegion] = useState('');
  const [shardService, setShardService] = useState('ec2');
  const [shardResourceIdsCsv, setShardResourceIdsCsv] = useState('');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const parsedServices = useMemo(() => csvToList(servicesCsv), [servicesCsv]);

  async function handleRunRecentlyTouched() {
    setError(null);
    setMessage(null);
    setIsSubmitting(true);
    try {
      const response = await enqueueReconcileRecentlyTouched({
        tenant_id: tenantId,
        lookback_minutes: lookbackMinutes,
        services: parsedServices,
        max_resources: maxResources,
      });
      setMessage(`Queued recently-touched reconciliation (${response.enqueued} job).`);
      await onSubmitted();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRunGlobal() {
    const confirmed = window.confirm('Run global reconciliation for this tenant? This may enqueue many jobs.');
    if (!confirmed) return;
    setError(null);
    setMessage(null);
    setIsSubmitting(true);
    try {
      const response = await enqueueReconcileInventoryGlobal({
        tenant_id: tenantId,
        account_ids: csvToList(globalAccountsCsv),
        regions: csvToList(globalRegionsCsv),
        services: parsedServices,
        max_resources: maxResources,
      });
      setMessage(`Queued global reconciliation shards: ${response.enqueued}.`);
      await onSubmitted();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRunShard() {
    if (!/^\d{12}$/.test(shardAccountId.trim())) {
      setError('Account ID must be 12 digits.');
      return;
    }
    if (!shardRegion.trim() || !shardService.trim()) {
      setError('Region and service are required for shard reconcile.');
      return;
    }
    setError(null);
    setMessage(null);
    setIsSubmitting(true);
    try {
      const response = await enqueueReconcileInventoryShard({
        shards: [
          {
            tenant_id: tenantId,
            account_id: shardAccountId.trim(),
            region: shardRegion.trim(),
            service: shardService.trim().toLowerCase(),
            resource_ids: csvToList(shardResourceIdsCsv),
            sweep_mode: 'targeted',
            max_resources: maxResources,
          },
        ],
      });
      setMessage(`Queued explicit shard reconciliation (${response.enqueued} shard).`);
      await onSubmitted();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-4 rounded-xl border border-border bg-surface p-4">
      <div>
        <h3 className="text-sm font-medium text-text">Reconciliation Controls</h3>
        <p className="mt-1 text-xs text-muted">Jobs are asynchronous and require the inventory worker pool.</p>
      </div>

      {!featureEnabled && (
        <div className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
          Reconcile actions are disabled. Set <code>NEXT_PUBLIC_CONTROL_PLANE_RECONCILE_UI_ENABLED=true</code> to enable.
          <div className="mt-1 text-xs text-warning/80">
            Current value: <code>{rawFlag ?? '(unset)'}</code>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <Input
          type="number"
          min={1}
          max={1440}
          value={String(lookbackMinutes)}
          onChange={(e) => setLookbackMinutes(Number(e.target.value) || 60)}
          placeholder="Lookback minutes"
        />
        <Input
          type="number"
          min={1}
          max={5000}
          value={String(maxResources)}
          onChange={(e) => setMaxResources(Number(e.target.value) || defaultMaxResources)}
          placeholder="Max resources"
        />
        <Input value={servicesCsv} onChange={(e) => setServicesCsv(e.target.value)} placeholder="Services CSV (ec2,s3,...)" />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" disabled={!featureEnabled || isSubmitting} onClick={handleRunRecentlyTouched}>
          Run Recently Touched
        </Button>
      </div>

      <div className="rounded-xl border border-border/60 p-3">
        <p className="text-xs font-medium text-muted">Global Reconcile</p>
        <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2">
          <Input value={globalAccountsCsv} onChange={(e) => setGlobalAccountsCsv(e.target.value)} placeholder="Account IDs CSV (optional)" />
          <Input value={globalRegionsCsv} onChange={(e) => setGlobalRegionsCsv(e.target.value)} placeholder="Regions CSV (optional)" />
        </div>
        <div className="mt-3">
          <Button variant="secondary" disabled={!featureEnabled || isSubmitting} onClick={handleRunGlobal}>
            Run Global Reconcile
          </Button>
        </div>
      </div>

      <div className="rounded-xl border border-border/60 p-3">
        <p className="text-xs font-medium text-muted">Explicit Shard Reconcile</p>
        <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2">
          <Input value={shardAccountId} onChange={(e) => setShardAccountId(e.target.value)} placeholder="Account ID (12 digits)" />
          <Input value={shardRegion} onChange={(e) => setShardRegion(e.target.value)} placeholder="Region (e.g. eu-north-1)" />
          <Input value={shardService} onChange={(e) => setShardService(e.target.value)} placeholder="Service (ec2, s3, ... )" />
          <Input value={shardResourceIdsCsv} onChange={(e) => setShardResourceIdsCsv(e.target.value)} placeholder="Resource IDs CSV (optional)" />
        </div>
        <div className="mt-3">
          <Button variant="secondary" disabled={!featureEnabled || isSubmitting} onClick={handleRunShard}>
            Run Shard Reconcile
          </Button>
        </div>
      </div>

      {message && <div className="rounded-xl border border-success/30 bg-success/10 p-3 text-sm text-success">{message}</div>}
      {error && <div className="rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{error}</div>}
    </div>
  );
}
