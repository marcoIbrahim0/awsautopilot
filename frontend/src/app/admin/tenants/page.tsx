'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useAuth } from '@/contexts/AuthContext';
import { getErrorMessage, getSaasSystemHealth, getSaasTenants, SaasSystemHealth, SaasTenantListItem } from '@/lib/api';
import { startNavigationFeedback } from '@/lib/navigation-feedback';

const PAGE_SIZE = 20;

export default function AdminTenantsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();
  const [items, setItems] = useState<SaasTenantListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState('');
  const [draftQuery, setDraftQuery] = useState('');
  const [health, setHealth] = useState<SaasSystemHealth | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent('/admin/tenants')}`);
      return;
    }
    if (!user?.is_saas_admin) {
      router.replace('/accounts');
      return;
    }
    let active = true;
    Promise.all([
      getSaasTenants({ query, limit: PAGE_SIZE, offset }),
      getSaasSystemHealth(),
    ])
      .then(([tenants, systemHealth]) => {
        if (!active) return;
        setItems(tenants.items);
        setTotal(tenants.total);
        setHealth(systemHealth);
      })
      .catch((err) => {
        if (!active) return;
        setError(getErrorMessage(err));
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading, isAuthenticated, user, query, offset, router]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <AppShell title="SaaS Admin">
      <div className="max-w-7xl mx-auto w-full space-y-6">
        <section className="bg-surface border border-border rounded-xl p-4">
          <div className="flex flex-wrap items-center gap-3">
            <Input
              value={draftQuery}
              onChange={(e) => setDraftQuery(e.target.value)}
              placeholder="Search tenant name or id"
              className="max-w-md"
            />
            <Button
              variant="secondary"
              onClick={() => {
                startNavigationFeedback();
                router.push('/admin/control-plane');
              }}
            >
              Control Plane Ops
            </Button>
            <Button
              onClick={() => {
                setOffset(0);
                setQuery(draftQuery.trim());
              }}
            >
              Search
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setDraftQuery('');
                setQuery('');
                setOffset(0);
              }}
            >
              Clear
            </Button>
          </div>
        </section>

        {health && (
          <section className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-6">
            <div className="bg-surface border border-border rounded-xl p-4">
              <p className="text-sm text-muted">Queue configured</p>
              <p className="text-lg font-semibold">{health.queue_configured ? 'Yes' : 'No'}</p>
            </div>
            <div className="bg-surface border border-border rounded-xl p-4">
              <p className="text-sm text-muted">Export bucket configured</p>
              <p className="text-lg font-semibold">{health.export_bucket_configured ? 'Yes' : 'No'}</p>
            </div>
            <div className="bg-surface border border-border rounded-xl p-4">
              <p className="text-sm text-muted">Support bucket configured</p>
              <p className="text-lg font-semibold">{health.support_bucket_configured ? 'Yes' : 'No'}</p>
            </div>
            <div className="bg-surface border border-border rounded-xl p-4">
              <p className="text-sm text-muted">Worker failure rate (24h)</p>
              <p className="text-lg font-semibold">{(health.worker_failure_rate_24h * 100).toFixed(2)}%</p>
            </div>
            <div className="bg-surface border border-border rounded-xl p-4">
              <p className="text-sm text-muted">Control-plane drop rate (24h)</p>
              <p className="text-lg font-semibold">{(health.control_plane_drop_rate_24h * 100).toFixed(2)}%</p>
            </div>
            <div className="bg-surface border border-border rounded-xl p-4">
              <p className="text-sm text-muted">p95 queue lag (24h)</p>
              <p className="text-lg font-semibold">
                {health.p95_queue_lag_ms_24h == null ? '—' : `${(health.p95_queue_lag_ms_24h / 1000).toFixed(2)}s`}
              </p>
            </div>
          </section>
        )}

        {error && (
          <div className="p-4 rounded-xl border border-danger/40 bg-danger/10 text-danger">
            {error}
          </div>
        )}

        <section className="bg-surface border border-border rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-bg/50 border-b border-border">
              <tr>
                <th className="text-left px-4 py-3">Tenant</th>
                <th className="text-left px-4 py-3">Users</th>
                <th className="text-left px-4 py-3">Accounts</th>
                <th className="text-left px-4 py-3">Open Findings</th>
                <th className="text-left px-4 py-3">Open Actions</th>
                <th className="text-left px-4 py-3">Last Activity</th>
                <th className="text-left px-4 py-3">Flags</th>
              </tr>
            </thead>
            <tbody>
              {!isLoading && items.length === 0 && (
                <tr>
                  <td className="px-4 py-4 text-muted" colSpan={7}>No tenants found.</td>
                </tr>
              )}
              {items.map((tenant) => (
                <tr key={tenant.tenant_id} className="border-b border-border/60 hover:bg-bg/40">
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => {
                        startNavigationFeedback();
                        router.push(`/admin/tenants/${tenant.tenant_id}`);
                      }}
                      className="text-left"
                    >
                      <p className="font-medium text-text">{tenant.tenant_name}</p>
                      <p className="text-xs text-muted font-mono">{tenant.tenant_id}</p>
                    </button>
                  </td>
                  <td className="px-4 py-3">{tenant.users_count}</td>
                  <td className="px-4 py-3">{tenant.aws_accounts_count}</td>
                  <td className="px-4 py-3">{tenant.open_findings_count}</td>
                  <td className="px-4 py-3">{tenant.open_actions_count}</td>
                  <td className="px-4 py-3 text-muted">{tenant.last_activity_at ? new Date(tenant.last_activity_at).toLocaleString() : '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      <span className="px-2 py-0.5 rounded bg-bg border border-border text-xs">{tenant.has_connected_accounts ? 'Connected' : 'No Accounts'}</span>
                      <span className="px-2 py-0.5 rounded bg-bg border border-border text-xs">{tenant.ingestion_stale ? 'Ingestion Stale' : 'Ingestion Fresh'}</span>
                      <span className="px-2 py-0.5 rounded bg-bg border border-border text-xs">{tenant.digest_enabled ? 'Digest On' : 'Digest Off'}</span>
                      <span className="px-2 py-0.5 rounded bg-bg border border-border text-xs">{tenant.slack_configured ? 'Slack On' : 'Slack Off'}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="flex items-center justify-between">
          <p className="text-sm text-muted">Page {currentPage} of {pageCount}</p>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset((v) => Math.max(0, v - PAGE_SIZE))}>
              Previous
            </Button>
            <Button variant="secondary" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset((v) => v + PAGE_SIZE)}>
              Next
            </Button>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
