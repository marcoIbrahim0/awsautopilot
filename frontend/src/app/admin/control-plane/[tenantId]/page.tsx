'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';

import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import {
  ControlPlaneKpiGrid,
  FindingComparisonTable,
  ReconcileActionsPanel,
  ReconcileJobTable,
  ShadowFindingComparisonTable,
  ShadowStateBreakdown,
  SloBurnBadge,
} from '@/components/control-plane';
import { useAuth } from '@/contexts/AuthContext';
import {
  ControlPlaneReconcileJob,
  ControlPlaneCompareResponse,
  ControlPlaneShadowCompareResponse,
  ControlPlaneShadowSummaryResponse,
  ControlPlaneSloResponse,
  getControlPlaneReconcileJobs,
  getControlPlaneCompare,
  getControlPlaneShadowCompare,
  getControlPlaneShadowSummary,
  getControlPlaneSlo,
  getErrorMessage,
} from '@/lib/api';

export const runtime = 'nodejs';

const DEFAULT_SERVICES = ['ec2', 's3', 'cloudtrail', 'config', 'iam', 'ebs', 'rds', 'eks', 'ssm'];

export default function AdminTenantControlPlanePage() {
  const params = useParams<{ tenantId: string }>();
  const tenantId = params?.tenantId;
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();

  const [hours, setHours] = useState(24);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const [slo, setSlo] = useState<ControlPlaneSloResponse | null>(null);
  const [shadow, setShadow] = useState<ControlPlaneShadowSummaryResponse | null>(null);
  const [compare, setCompare] = useState<ControlPlaneCompareResponse | null>(null);
  const [selectedControl, setSelectedControl] = useState<string | null>(null);
  const [shadowCompare, setShadowCompare] = useState<ControlPlaneShadowCompareResponse | null>(null);
  const [shadowCompareLoading, setShadowCompareLoading] = useState(false);
  const [shadowCompareError, setShadowCompareError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<ControlPlaneReconcileJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [compareOffset, setCompareOffset] = useState(0);
  const [onlyWithShadow, setOnlyWithShadow] = useState(false);
  const [onlyMismatches, setOnlyMismatches] = useState(false);
  const compareLimit = 50;
  const shadowCompareLimit = 50;
  const [shadowCompareOffset, setShadowCompareOffset] = useState(0);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const [sloData, shadowData, compareData, jobsData] = await Promise.all([
        getControlPlaneSlo({ tenant_id: tenantId, hours }),
        getControlPlaneShadowSummary({ tenant_id: tenantId }),
        getControlPlaneCompare({
          tenant_id: tenantId,
          basis: 'live',
          only_with_shadow: onlyWithShadow || undefined,
          only_mismatches: onlyMismatches || undefined,
          limit: compareLimit,
          offset: compareOffset,
        }),
        getControlPlaneReconcileJobs({ tenant_id: tenantId, limit: 50 }),
      ]);
      setSlo(sloData);
      setShadow(shadowData);
      setCompare(compareData);
      setJobs(jobsData.items);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [tenantId, hours, compareLimit, compareOffset, onlyWithShadow, onlyMismatches]);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.replace('/login');
      return;
    }
    if (!user?.is_saas_admin) {
      router.replace('/accounts');
      return;
    }
    load().catch(() => undefined);
  }, [authLoading, isAuthenticated, user, tenantId, hours, refreshTick, router, load]);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(() => setRefreshTick((v) => v + 1), 30000);
    return () => clearInterval(timer);
  }, [autoRefresh]);

  const loadShadowCompare = useCallback(async () => {
    if (!tenantId || !selectedControl) {
      setShadowCompare(null);
      return;
    }
    setShadowCompareLoading(true);
    setShadowCompareError(null);
    try {
      const shadowData = await getControlPlaneShadowCompare({
        tenant_id: tenantId,
        control_id: selectedControl,
        limit: shadowCompareLimit,
        offset: shadowCompareOffset,
      });
      setShadowCompare(shadowData);
    } catch (err) {
      setShadowCompareError(getErrorMessage(err));
    } finally {
      setShadowCompareLoading(false);
    }
  }, [tenantId, selectedControl, shadowCompareLimit, shadowCompareOffset]);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated || !user?.is_saas_admin) return;
    loadShadowCompare().catch(() => undefined);
  }, [authLoading, isAuthenticated, user, loadShadowCompare]);

  return (
    <AppShell title={`Control Plane Tenant: ${tenantId ?? ''}`}>
      <div className="mx-auto w-full max-w-7xl space-y-6">
        <section className="flex flex-wrap items-center gap-2">
          <Link href="/admin/control-plane" className="text-accent hover:underline">Back to global</Link>
          {[1, 6, 24, 72, 168].map((value) => (
            <Button
              key={value}
              variant={hours === value ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setHours(value)}
            >
              {value === 168 ? '7d' : `${value}h`}
            </Button>
          ))}
          <label className="ml-2 flex items-center gap-2 text-sm text-muted">
            <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
            Auto refresh (30s)
          </label>
          <Button variant="secondary" size="sm" onClick={() => setRefreshTick((v) => v + 1)}>Refresh now</Button>
        </section>

        {error && <div className="rounded-xl border border-danger/30 bg-danger/10 p-4 text-danger">{error}</div>}
        {loading && <div className="rounded-xl border border-border bg-surface p-4 text-muted">Loading tenant control-plane data…</div>}

        {slo && (
          <>
            <ControlPlaneKpiGrid slo={slo} />
            <section className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <SloBurnBadge label="p95 Freshness Target (<5 min)" valueMs={slo.p95_end_to_end_lag_ms} targetMs={5 * 60 * 1000} />
              <SloBurnBadge label="p95 Resolution Target (<5 min)" valueMs={slo.p95_resolution_freshness_ms} targetMs={5 * 60 * 1000} />
            </section>
          </>
        )}

        {shadow && (
          <ShadowStateBreakdown
            summary={shadow}
            onControlSelect={(controlId) => {
              setSelectedControl(controlId);
              setShadowCompareOffset(0);
            }}
          />
        )}

        {selectedControl && (
          <section className="rounded-xl border border-border bg-surface p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-medium text-text">Shadow drill-down</h2>
                <p className="text-xs text-muted">
                  Control: <span className="font-mono text-text">{selectedControl}</span>
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setSelectedControl(null);
                  setShadowCompare(null);
                  setShadowCompareOffset(0);
                }}
              >
                Clear
              </Button>
            </div>
            {shadowCompareError && (
              <div className="mt-3 rounded-xl border border-danger/30 bg-danger/10 p-3 text-danger">
                {shadowCompareError}
              </div>
            )}
            {shadowCompareLoading && (
              <div className="mt-3 rounded-xl border border-border bg-surface p-3 text-muted">
                Loading shadow rows…
              </div>
            )}
          </section>
        )}

        {selectedControl && shadowCompare && (
          <ShadowFindingComparisonTable
            items={shadowCompare.items}
            total={shadowCompare.total}
            offset={shadowCompareOffset}
            limit={shadowCompareLimit}
            onPageChange={(nextOffset) => setShadowCompareOffset(nextOffset)}
          />
        )}

        {compare && (
          <FindingComparisonTable
            basis={compare.basis}
            items={compare.items}
            total={compare.total}
            offset={compareOffset}
            limit={compareLimit}
            onPageChange={(nextOffset) => setCompareOffset(nextOffset)}
            onlyWithShadow={onlyWithShadow}
            onOnlyWithShadowChange={(value) => {
              setCompareOffset(0);
              setOnlyWithShadow(value);
            }}
            onlyMismatches={onlyMismatches}
            onOnlyMismatchesChange={(value) => {
              setCompareOffset(0);
              setOnlyMismatches(value);
            }}
          />
        )}

        {tenantId && (
          <ReconcileActionsPanel
            tenantId={tenantId}
            defaultServices={DEFAULT_SERVICES}
            defaultMaxResources={500}
            onSubmitted={async () => {
              await load();
            }}
          />
        )}

        <ReconcileJobTable jobs={jobs} />
      </div>
    </AppShell>
  );
}
