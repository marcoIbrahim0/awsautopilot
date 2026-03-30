'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { Badge, getStatusBadgeVariant } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { remediationInsetClass } from '@/components/ui/remediation-surface';
import { useAuth } from '@/contexts/AuthContext';
import { getAccounts, getErrorMessage, type AwsAccount } from '@/lib/api';
import { SettingsCard, SettingsNotice, SettingsSectionIntro } from './settings-ui';

function formatDate(value: string | null): string {
  if (!value) return 'Never';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function OrganizationSettingsTab() {
  const { isAuthenticated, tenant, saas_account_id } = useAuth();
  const [accounts, setAccounts] = useState<AwsAccount[]>([]);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAccounts = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingAccounts(true);
    setError(null);
    try {
      setAccounts(await getAccounts());
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoadingAccounts(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void fetchAccounts();
  }, [fetchAccounts]);

  const summary = useMemo(() => {
    const validated = accounts.filter((account) => account.status === 'validated').length;
    const pending = accounts.filter((account) => account.status === 'pending').length;
    const disabled = accounts.filter((account) => account.status === 'disabled').length;
    const attention = accounts.filter((account) => !['validated', 'pending', 'disabled'].includes(account.status)).length;
    const totalRegions = new Set(accounts.flatMap((account) => account.regions)).size;
    return { validated, pending, disabled, attention, totalRegions };
  }, [accounts]);

  return (
    <div id="settings-panel-organization" role="tabpanel" tabIndex={0} className="space-y-6">
      <SettingsSectionIntro
        title="Organization"
        description="Review tenant metadata, connected-account coverage, and the handoff points into Accounts and onboarding final checks."
        action={
          <>
            <Link href="/accounts" className="inline-flex">
              <Button variant="secondary">Open accounts</Button>
            </Link>
            <Link href="/onboarding" className="inline-flex">
              <Button>Open onboarding final checks</Button>
            </Link>
          </>
        }
      />

      <SettingsNotice tone="info">
        Account connection health and final verification stay in onboarding. Settings is now a read-only handoff
        surface for tenant metadata and account coverage.
      </SettingsNotice>

      {error ? <SettingsNotice tone="danger">{error}</SettingsNotice> : null}

      <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-6">
          <SettingsCard>
            <h3 className="text-base font-semibold text-text">Tenant metadata</h3>
            <div className="mt-4 space-y-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Tenant name</p>
                <p className="mt-1 text-sm text-text">{tenant?.name || '—'}</p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Tenant ID</p>
                <code className="mt-1 block overflow-x-auto rounded border border-border bg-bg/60 px-3 py-2 text-xs text-text">
                  {tenant?.id || '—'}
                </code>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted">External ID</p>
                <code className="mt-1 block overflow-x-auto rounded border border-border bg-bg/60 px-3 py-2 text-xs text-text">
                  {tenant?.external_id || '—'}
                </code>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Platform account ID</p>
                <code className="mt-1 block overflow-x-auto rounded border border-border bg-bg/60 px-3 py-2 text-xs text-text">
                  {saas_account_id || '—'}
                </code>
              </div>
            </div>
          </SettingsCard>

          <SettingsCard>
            <h3 className="text-base font-semibold text-text">Connected-account summary</h3>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className={remediationInsetClass('default', 'p-4')}>
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Total accounts</p>
                <p className="mt-2 text-2xl font-semibold text-text">{accounts.length}</p>
              </div>
              <div className={remediationInsetClass('default', 'p-4')}>
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Monitored regions</p>
                <p className="mt-2 text-2xl font-semibold text-text">{summary.totalRegions}</p>
              </div>
              <div className={remediationInsetClass('default', 'p-4')}>
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Validated</p>
                <p className="mt-2 text-2xl font-semibold text-text">{summary.validated}</p>
              </div>
              <div className={remediationInsetClass('default', 'p-4')}>
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Needs attention</p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {summary.pending + summary.disabled + summary.attention}
                </p>
              </div>
            </div>
          </SettingsCard>
        </div>

        <SettingsCard className="overflow-hidden p-0">
          <div className="border-b border-border px-6 py-4">
            <h3 className="text-base font-semibold text-text">Connected accounts</h3>
            <p className="text-sm text-muted">
              Review connection status here, then use Accounts for operational changes and onboarding for final checks.
            </p>
          </div>

          {isLoadingAccounts ? (
            <div className="p-8 text-center">
              <p className="animate-pulse text-muted">Loading connected accounts...</p>
            </div>
          ) : accounts.length === 0 ? (
            <div className="space-y-4 p-8 text-center">
              <p className="text-muted">No AWS accounts are connected yet.</p>
              <div className="flex justify-center gap-3">
                <Link href="/accounts" className="inline-flex">
                  <Button variant="secondary">Open accounts</Button>
                </Link>
                <Link href="/onboarding" className="inline-flex">
                  <Button>Start onboarding</Button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {accounts.map((account) => (
                <div key={account.id} className="space-y-4 px-6 py-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-sm font-semibold text-text">{account.account_id}</p>
                      <p className="mt-1 text-sm text-muted">
                        {account.regions.length} region{account.regions.length === 1 ? '' : 's'} monitored
                      </p>
                    </div>
                    <Badge variant={getStatusBadgeVariant(account.status)}>{account.status}</Badge>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <div className={remediationInsetClass('default', 'p-4')}>
                      <p className="text-xs font-medium uppercase tracking-wide text-muted">Read role ARN</p>
                      <code className="mt-2 block break-all text-xs text-text">{account.role_read_arn}</code>
                    </div>
                    <div className={remediationInsetClass('default', 'p-4')}>
                      <p className="text-xs font-medium uppercase tracking-wide text-muted">Last validated</p>
                      <p className="mt-2 text-sm text-text">{formatDate(account.last_validated_at)}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </SettingsCard>
      </div>
    </div>
  );
}
