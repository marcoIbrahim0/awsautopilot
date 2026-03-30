'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { ControlPlaneKpiGrid, SloBurnBadge } from '@/components/control-plane';
import { useAuth } from '@/contexts/AuthContext';
import {
  ControlPlaneSloResponse,
  SaasTenantListItem,
  getControlPlaneSlo,
  getErrorMessage,
  getSaasTenants,
} from '@/lib/api';
import { startNavigationFeedback } from '@/lib/navigation-feedback';

const HOURS_OPTIONS = [1, 6, 24, 72, 168] as const;

interface TenantSloRow {
  tenant: SaasTenantListItem;
  slo: ControlPlaneSloResponse;
}

export default function AdminControlPlanePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();

  const [hours, setHours] = useState<number>(24);
  const [tenantFilter, setTenantFilter] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);

  const [tenants, setTenants] = useState<SaasTenantListItem[]>([]);
  const [globalSlo, setGlobalSlo] = useState<ControlPlaneSloResponse | null>(null);
  const [tenantRows, setTenantRows] = useState<TenantSloRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAdminAllowed, setIsAdminAllowed] = useState(true);

  const topRows = useMemo(() => {
    return [...tenantRows]
      .sort((a, b) => {
        const aLag = a.slo.p95_end_to_end_lag_ms ?? -1;
        const bLag = b.slo.p95_end_to_end_lag_ms ?? -1;
        return bLag - aLag;
      })
      .slice(0, 10);
  }, [tenantRows]);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent('/admin/control-plane')}`);
      return;
    }
    if (!user?.is_saas_admin) {
      setIsAdminAllowed(false);
      setLoading(false);
      return;
    }
    setIsAdminAllowed(true);

    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [tenantResponse, sloResponse] = await Promise.all([
          getSaasTenants({ limit: 20, offset: 0 }),
          getControlPlaneSlo({ tenant_id: tenantFilter || undefined, hours }),
        ]);
        if (!active) return;
        setTenants(tenantResponse.items);
        setGlobalSlo(sloResponse);

        const candidates = tenantFilter
          ? tenantResponse.items.filter((t) => t.tenant_id === tenantFilter)
          : tenantResponse.items.slice(0, 10);

        const settled = await Promise.allSettled(
          candidates.map(async (tenant) => {
            const tenantSlo = await getControlPlaneSlo({ tenant_id: tenant.tenant_id, hours });
            return { tenant, slo: tenantSlo };
          })
        );
        const rows = settled
          .filter((result): result is PromiseFulfilledResult<TenantSloRow> => result.status === 'fulfilled')
          .map((result) => result.value);
        if (!active) return;
        setTenantRows(rows);
      } catch (err) {
        if (!active) return;
        setError(getErrorMessage(err));
      } finally {
        if (active) setLoading(false);
      }
    }

    load().catch(() => undefined);
    return () => {
      active = false;
    };
  }, [authLoading, isAuthenticated, user, router, hours, tenantFilter, refreshTick]);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(() => {
      setRefreshTick((v) => v + 1);
    }, 30000);
    return () => clearInterval(timer);
  }, [autoRefresh]);

  return (
    <AppShell title="Control Plane Ops">
      <div className="mx-auto w-full max-w-7xl space-y-6">
        {!isAdminAllowed && (
          <div className="rounded-xl border border-warning/30 bg-warning/10 p-4 text-warning">
            SaaS admin access is required for control-plane metrics.
          </div>
        )}

        <section className="rounded-xl border border-border bg-surface p-4">
          <div className="flex flex-wrap items-center gap-2">
            {HOURS_OPTIONS.map((value) => (
              <Button
                key={value}
                variant={hours === value ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => setHours(value)}
              >
                {value === 168 ? '7d' : `${value}h`}
              </Button>
            ))}
            <Input
              className="max-w-md"
              value={tenantFilter}
              onChange={(e) => setTenantFilter(e.target.value.trim())}
              placeholder="Optional tenant UUID filter"
            />
            <label className="ml-2 flex items-center gap-2 text-sm text-muted">
              <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
              Auto refresh (30s)
            </label>
            <Button variant="secondary" size="sm" onClick={() => setRefreshTick((v) => v + 1)}>Refresh now</Button>
          </div>
        </section>

        {error && <div className="rounded-xl border border-danger/30 bg-danger/10 p-4 text-danger">{error}</div>}

        {loading && <div className="rounded-xl border border-border bg-surface p-4 text-muted">Loading control-plane metrics…</div>}

        {isAdminAllowed && globalSlo && (
          <>
            <ControlPlaneKpiGrid slo={globalSlo} />

            <section className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <SloBurnBadge label="p95 Freshness Target (<5 min)" valueMs={globalSlo.p95_end_to_end_lag_ms} targetMs={5 * 60 * 1000} />
              <SloBurnBadge label="p99 Freshness Target (<10 min)" valueMs={globalSlo.p99_end_to_end_lag_ms} targetMs={10 * 60 * 1000} />
            </section>

            <section className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <Tile label="Success Events" value={globalSlo.success_events} />
              <Tile label="Dropped Events" value={globalSlo.dropped_events} />
              <Tile label="Duplicate Hits" value={globalSlo.duplicate_hits} />
            </section>
          </>
        )}

        {isAdminAllowed && (
        <section className="rounded-xl border border-border bg-surface p-4">
          <h2 className="text-sm font-medium text-text">Top Affected Tenants</h2>
          <div className="mt-3 overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted">
                  <th className="py-2 pr-3">Tenant</th>
                  <th className="py-2 pr-3">p95 End-to-End</th>
                  <th className="py-2 pr-3">Drop Rate</th>
                  <th className="py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {topRows.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-3 text-muted">No tenant-level SLO rows available.</td>
                  </tr>
                )}
                {topRows.map((row) => (
                  <tr key={row.tenant.tenant_id} className="border-t border-border/60">
                    <td className="py-2 pr-3">
                      <p className="font-medium text-text">{row.tenant.tenant_name}</p>
                      <p className="font-mono text-xs text-muted">{row.tenant.tenant_id}</p>
                    </td>
                    <td className="py-2 pr-3">{row.slo.p95_end_to_end_lag_ms == null ? '—' : `${(row.slo.p95_end_to_end_lag_ms / 60000).toFixed(2)} min`}</td>
                    <td className="py-2 pr-3">{(row.slo.drop_rate * 100).toFixed(2)}%</td>
                    <td className="py-2">
                      <Link
                        href={`/admin/control-plane/${row.tenant.tenant_id}`}
                        onClick={() => startNavigationFeedback()}
                        className="text-accent hover:underline"
                      >
                        Open Tenant View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        )}

        {isAdminAllowed && (
        <section className="rounded-xl border border-border bg-surface p-4">
          <h2 className="text-sm font-medium text-text">Known Tenants</h2>
          <p className="mt-1 text-xs text-muted">Use any tenant ID above to filter or drill down.</p>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            {tenants.map((tenant) => (
              <button
                key={tenant.tenant_id}
                type="button"
                onClick={() => setTenantFilter(tenant.tenant_id)}
                className="rounded-lg border border-border/70 bg-bg px-3 py-2 text-left hover:border-accent/40"
              >
                <p className="text-sm font-medium text-text">{tenant.tenant_name}</p>
                <p className="font-mono text-xs text-muted">{tenant.tenant_id}</p>
              </button>
            ))}
          </div>
        </section>
        )}
      </div>
    </AppShell>
  );
}

function Tile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold text-text">{value}</p>
    </div>
  );
}
