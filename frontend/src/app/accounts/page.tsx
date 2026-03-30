'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';

import { AppShell } from '@/components/layout';
import { NeedHelpLink } from '@/components/help/NeedHelpLink';
import { TenantIdForm } from '@/components/TenantIdForm';
import { Button } from '@/components/ui/Button';
import { ButtonLink } from '@/components/ui/ButtonLink';
import { Badge, getStatusBadgeVariant } from '@/components/ui/Badge';
import {
  REMEDIATION_EYEBROW_CLASS,
  RemediationCallout,
  RemediationPanel,
  RemediationSection,
  RemediationStatCard,
  SectionTitleExplainer,
  remediationInsetClass,
  remediationPanelClass,
} from '@/components/ui/remediation-surface';
import { useAuth } from '@/contexts/AuthContext';
import { AwsAccount, getAccounts, getErrorMessage } from '@/lib/api';
import { useTenantId } from '@/lib/tenant';
import { cn } from '@/lib/utils';
import { AccountDetailModal } from './AccountDetailModal';
import { ConnectAccountModal } from './ConnectAccountModal';
import { AccountRowActions } from './AccountRowActions';
import { formatUtcDateTime } from './date-format';

type AccountSection = 'health' | 'roles' | 'integrations' | 'usage';

const ACCOUNT_SECTIONS: { key: AccountSection; label: string; summary: string }[] = [
  {
    key: 'health',
    label: 'Connection health',
    summary: 'Live validation state, regions, and quick operator actions.',
  },
  {
    key: 'roles',
    label: 'Roles & permissions',
    summary: 'ReadRole posture and monitored-region scope across connected accounts.',
  },
  {
    key: 'integrations',
    label: 'Integrations',
    summary: 'Required service checks and onboarding handoff for each account.',
  },
  {
    key: 'usage',
    label: 'Usage & lifecycle',
    summary: 'Lifecycle timestamps and monitoring posture over time.',
  },
];

function canManageAccounts(isAuthenticated: boolean, tenantId: string | null): boolean {
  return isAuthenticated || !!tenantId;
}

function formatDate(dateString: string | null): string {
  return formatUtcDateTime(dateString);
}

function healthLabel(account: AwsAccount): { label: string; variant: 'success' | 'warning' | 'danger' | 'default' } {
  const status = account.status.toLowerCase();
  if (status === 'validated') return { label: 'Healthy', variant: 'success' };
  if (status === 'disabled') return { label: 'Paused', variant: 'default' };
  if (status === 'pending') return { label: 'Onboarding required', variant: 'warning' };
  return { label: 'Needs attention', variant: 'danger' };
}

function renderSurfaceMessage(message: string) {
  return (
    <div className={remediationPanelClass('default', 'p-8 text-center text-sm text-muted')}>
      {message}
    </div>
  );
}

function AccountSectionTabs({
  activeSection,
  onSelect,
}: {
  activeSection: AccountSection;
  onSelect: (section: AccountSection) => void;
}) {
  return (
    <RemediationPanel className="p-2">
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4" role="tablist" aria-label="Account sections">
        {ACCOUNT_SECTIONS.map((section) => {
          const isActive = section.key === activeSection;
          return (
            <button
              key={section.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => onSelect(section.key)}
              className={cn(
                'rounded-[1.4rem] border px-4 py-3 text-left transition duration-200',
                isActive
                  ? 'border-accent/24 bg-accent/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
                  : 'border-border/45 bg-bg/45 hover:border-border/70 hover:bg-bg/65',
              )}
            >
              <p className="text-sm font-semibold text-text">{section.label}</p>
              <p className="mt-1 text-xs leading-5 text-text/68">{section.summary}</p>
            </button>
          );
        })}
      </div>
    </RemediationPanel>
  );
}

function AccountsHero({
  summary,
  onConnect,
}: {
  summary: { total: number; healthy: number; attention: number; totalRegions: number };
  onConnect: () => void;
}) {
  return (
    <RemediationSection
      eyebrow="Account hub"
      title="Connected AWS accounts"
      titleExplainer={<SectionTitleExplainer conceptId="connected_aws_accounts" context="accounts" label="Connected AWS accounts" />}
      description="Operate onboarding handoff, refresh findings, and manage connected-account lifecycle from the same dashboard surface language used by the rest of the product."
      tone="accent"
      action={
        <div className="flex flex-wrap items-center gap-2">
          <ButtonLink href="/onboarding" variant="secondary" size="sm">
            Run onboarding checks
          </ButtonLink>
          <NeedHelpLink from="/accounts" label="Need help?" variant="secondary" />
          <Button onClick={onConnect}>Connect AWS account</Button>
        </div>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className={remediationInsetClass('accent', 'space-y-4')}>
          <div>
            <p className={REMEDIATION_EYEBROW_CLASS}>Operator flow</p>
            <h3 className="mt-3 text-xl font-semibold text-text">
              Validate once in onboarding, operate continuously from Accounts.
            </h3>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-text/72">
              This surface is optimized for live account operations: confirm connection state, refresh data sources,
              inspect role posture, and hand operators back to onboarding whenever a required verification must be rerun.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <div className={remediationInsetClass('default', 'p-4')}>
              <p className={REMEDIATION_EYEBROW_CLASS}>Quick action</p>
              <p className="mt-3 text-sm font-medium text-text">Open details for refresh, reconciliation, and lifecycle actions.</p>
            </div>
            <div className={remediationInsetClass('default', 'p-4')}>
              <p className={REMEDIATION_EYEBROW_CLASS}>Required checks</p>
              <p className="mt-3 text-sm font-medium text-text">Inspector, Security Hub, AWS Config, and forwarder validation stay in onboarding.</p>
            </div>
            <div className={remediationInsetClass('default', 'p-4')}>
              <p className={REMEDIATION_EYEBROW_CLASS}>Connection contract</p>
              <p className="mt-3 text-sm font-medium text-text">Accounts stores ReadRole scope and regions; onboarding final checks confirm readiness.</p>
            </div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <RemediationStatCard
            label="Total accounts"
            labelExplainer={<SectionTitleExplainer conceptId="connected_aws_accounts" context="accounts" label="Total accounts" />}
            value={summary.total}
            detail="Accounts currently registered to this tenant."
          />
          <RemediationStatCard
            label="Healthy"
            labelExplainer={<SectionTitleExplainer conceptId="connection_health" context="accounts" label="Healthy" />}
            value={summary.healthy}
            detail="Validated accounts ready for ingest and reconciliation."
          />
          <RemediationStatCard
            label="Needs attention"
            labelExplainer={<SectionTitleExplainer conceptId="connection_health" context="accounts" label="Needs attention" />}
            value={summary.attention}
            detail="Accounts pending validation, paused, or requiring follow-up."
          />
          <RemediationStatCard
            label="Monitored regions"
            labelExplainer={<SectionTitleExplainer conceptId="monitored_regions" context="accounts" label="Monitored regions" />}
            value={summary.totalRegions}
            detail="Distinct AWS regions currently in scope across all accounts."
          />
        </div>
      </div>
    </RemediationSection>
  );
}

function AccountHealthTable({
  accounts,
  tenantId,
  onOpenDetails,
  onUpdate,
}: {
  accounts: AwsAccount[];
  tenantId?: string;
  onOpenDetails: (account: AwsAccount) => void;
  onUpdate: () => void;
}) {
  return (
    <RemediationSection
      eyebrow="Connection health"
      title="Connection state and quick account actions"
      titleExplainer={<SectionTitleExplainer conceptId="connection_health" context="accounts" label="Connection state and quick account actions" />}
      description="Open the account detail workflow, rerun onboarding-only checks, or queue source refreshes directly from the health grid."
      action={<Badge variant="info">{accounts.length} account{accounts.length === 1 ? '' : 's'}</Badge>}
    >
      <div className="overflow-hidden rounded-[1.6rem] border border-border/45 bg-bg/35">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-bg/65 text-left">
              <tr>
                <th className="px-5 py-4 font-semibold text-text">Account</th>
                <th className="px-5 py-4 font-semibold text-text">Coverage</th>
                <th className="px-5 py-4 font-semibold text-text">Status</th>
                <th className="px-5 py-4 font-semibold text-text">Connection health</th>
                <th className="px-5 py-4 font-semibold text-text">Last validated</th>
                <th className="px-5 py-4 font-semibold text-text">Actions</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => {
                const health = healthLabel(account);
                return (
                  <tr key={account.id} className="border-t border-border/35 align-top">
                    <td className="px-5 py-4">
                      <button
                        type="button"
                        onClick={() => onOpenDetails(account)}
                        className="text-left transition hover:text-accent"
                      >
                        <span className="font-mono text-sm font-semibold text-text">{account.account_id}</span>
                        <span className="mt-1 block text-xs text-muted">Open detail workflow</span>
                      </button>
                    </td>
                    <td className="px-5 py-4 text-text/74">
                      <p className="font-medium text-text">{account.regions.length} region{account.regions.length === 1 ? '' : 's'}</p>
                      <p className="mt-1 text-xs text-muted">{account.regions.join(', ')}</p>
                    </td>
                    <td className="px-5 py-4">
                      <Badge variant={getStatusBadgeVariant(account.status)}>{account.status}</Badge>
                    </td>
                    <td className="px-5 py-4">
                      <Badge variant={health.variant}>{health.label}</Badge>
                    </td>
                    <td className="px-5 py-4 text-text/74">{formatDate(account.last_validated_at)}</td>
                    <td className="px-5 py-4">
                      <AccountRowActions
                        account={account}
                        tenantId={tenantId}
                        onUpdate={onUpdate}
                        onOpenDetails={() => onOpenDetails(account)}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </RemediationSection>
  );
}

function AccountRolesGrid({
  accounts,
  onOpenDetails,
}: {
  accounts: AwsAccount[];
  onOpenDetails: (account: AwsAccount) => void;
}) {
  return (
    <RemediationSection
      eyebrow="Roles & permissions"
      title="ReadRole posture"
      titleExplainer={<SectionTitleExplainer conceptId="read_role_posture" context="accounts" label="ReadRole posture" />}
      description="Review the connected ReadRole configuration for each account and use account details for reconnect or lifecycle actions."
      action={<Badge variant="info">{accounts.length} configured</Badge>}
    >
      <div className="grid gap-4 lg:grid-cols-2">
        {accounts.map((account) => (
          <RemediationPanel key={account.id} className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className={REMEDIATION_EYEBROW_CLASS}>AWS account</p>
                <p className="mt-3 font-mono text-lg font-semibold text-text">{account.account_id}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant={getStatusBadgeVariant(account.status)}>{account.status}</Badge>
                <Badge variant="info">
                  {account.regions.length} region{account.regions.length === 1 ? '' : 's'}
                </Badge>
              </div>
            </div>

            <div className="mt-5 grid gap-3">
              <div className={remediationInsetClass('default', 'p-4')}>
                <p className={REMEDIATION_EYEBROW_CLASS}>Read role ARN</p>
                <p className="mt-3 break-all font-mono text-xs text-text">{account.role_read_arn}</p>
              </div>
              <div className={remediationInsetClass('default', 'p-4')}>
                <p className={REMEDIATION_EYEBROW_CLASS}>Last validated</p>
                <p className="mt-3 text-sm text-text">{formatDate(account.last_validated_at)}</p>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-text/72">Regions: {account.regions.join(', ')}</p>
              <Button variant="secondary" size="sm" onClick={() => onOpenDetails(account)}>
                Review account
              </Button>
            </div>
          </RemediationPanel>
        ))}
      </div>
    </RemediationSection>
  );
}

function AccountIntegrationsGrid({
  accounts,
}: {
  accounts: AwsAccount[];
}) {
  return (
    <RemediationSection
      eyebrow="Integrations"
      title="Required service checks and onboarding handoff"
      titleExplainer={<SectionTitleExplainer conceptId="required_service_checks" context="accounts" label="Required service checks and onboarding handoff" />}
      description="Accounts uses onboarding for required service verification so the validation story stays explicit and auditable."
      tone="info"
    >
      <div className="space-y-4">
        <RemediationCallout
          tone="info"
          title="Validation boundary"
          description="Required checks remain the same across the product: Inspector, Security Hub, AWS Config, and the control-plane forwarder. Access Analyzer remains optional and can be enabled later."
        />
        <div className="grid gap-4 lg:grid-cols-2">
          {accounts.map((account) => (
            <RemediationPanel key={account.id} className="p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Account</p>
                  <p className="mt-3 font-mono text-lg font-semibold text-text">{account.account_id}</p>
                </div>
                <Badge variant={getStatusBadgeVariant(account.status)}>{account.status}</Badge>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-2">
                <div className={remediationInsetClass('default', 'p-4')}>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Required checks</p>
                  <p className="mt-3 text-sm leading-6 text-text/74">Inspector, Security Hub, AWS Config, and forwarder.</p>
                </div>
                <div className={remediationInsetClass('default', 'p-4')}>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Optional follow-up</p>
                  <p className="mt-3 text-sm leading-6 text-text/74">Access Analyzer can be enabled later without blocking onboarding completion.</p>
                </div>
              </div>

            <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-text/72">Monitored regions: {account.regions.join(', ')}</p>
              <ButtonLink href="/onboarding" variant="secondary" size="sm">
                Open onboarding checks
              </ButtonLink>
            </div>
          </RemediationPanel>
        ))}
        </div>
      </div>
    </RemediationSection>
  );
}

function AccountUsageTable({ accounts }: { accounts: AwsAccount[] }) {
  return (
    <RemediationSection
      eyebrow="Usage & lifecycle"
      title="Lifecycle timestamps and monitoring posture"
      titleExplainer={<SectionTitleExplainer conceptId="lifecycle_timestamps" context="accounts" label="Lifecycle timestamps and monitoring posture" />}
      description="Use this timeline view when you need to understand when an account was connected, updated, or last validated."
    >
      <div className="overflow-hidden rounded-[1.6rem] border border-border/45 bg-bg/35">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-bg/65 text-left">
              <tr>
                <th className="px-5 py-4 font-semibold text-text">Account</th>
                <th className="px-5 py-4 font-semibold text-text">Created</th>
                <th className="px-5 py-4 font-semibold text-text">Updated</th>
                <th className="px-5 py-4 font-semibold text-text">Last validated</th>
                <th className="px-5 py-4 font-semibold text-text">Lifecycle</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.id} className="border-t border-border/35">
                  <td className="px-5 py-4 font-mono font-medium text-text">{account.account_id}</td>
                  <td className="px-5 py-4 text-text/74">{formatDate(account.created_at)}</td>
                  <td className="px-5 py-4 text-text/74">{formatDate(account.updated_at)}</td>
                  <td className="px-5 py-4 text-text/74">{formatDate(account.last_validated_at)}</td>
                  <td className="px-5 py-4">
                    <Badge variant={account.status === 'disabled' ? 'default' : 'success'}>
                      {account.status === 'disabled' ? 'Paused' : 'Live'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </RemediationSection>
  );
}

export default function AccountsPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { tenantId, setTenantId } = useTenantId();

  const [accounts, setAccounts] = useState<AwsAccount[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [detailAccount, setDetailAccount] = useState<AwsAccount | null>(null);
  const [reconnectAccount, setReconnectAccount] = useState<AwsAccount | null>(null);
  const [activeSection, setActiveSection] = useState<AccountSection>('health');

  const showContent = canManageAccounts(isAuthenticated, tenantId);

  const fetchAccounts = useCallback(async () => {
    if (!showContent) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const data = await getAccounts(isAuthenticated ? undefined : tenantId ?? undefined);
      setAccounts(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, showContent, tenantId]);

  useEffect(() => {
    if (authLoading) return;
    void fetchAccounts();
  }, [authLoading, fetchAccounts]);

  const summary = useMemo(() => {
    const healthy = accounts.filter((account) => account.status.toLowerCase() === 'validated').length;
    const attention = accounts.filter((account) => account.status.toLowerCase() !== 'validated').length;
    const totalRegions = new Set(accounts.flatMap((account) => account.regions)).size;
    return {
      total: accounts.length,
      healthy,
      attention,
      totalRegions,
    };
  }, [accounts]);

  const emptyState = (
    <RemediationSection
      eyebrow="Account hub"
      title="No AWS accounts connected yet"
      titleExplainer={<SectionTitleExplainer conceptId="connected_aws_accounts" context="accounts" label="No AWS accounts connected yet" />}
      description="Connect your first account to start ingestion, run onboarding validations, and unlock remediation planning."
      tone="accent"
      action={<Button onClick={() => setIsModalOpen(true)}>Connect first account</Button>}
    >
      <RemediationCallout
        tone="info"
        title="What happens next"
        description="Deploy the ReadRole stack, save the ARN and monitored regions, then use onboarding final checks to confirm service readiness."
      />
    </RemediationSection>
  );

  const contentBySection = {
    health: (
      <AccountHealthTable
        accounts={accounts}
        tenantId={tenantId ?? undefined}
        onOpenDetails={setDetailAccount}
        onUpdate={fetchAccounts}
      />
    ),
    roles: <AccountRolesGrid accounts={accounts} onOpenDetails={setDetailAccount} />,
    integrations: <AccountIntegrationsGrid accounts={accounts} />,
    usage: <AccountUsageTable accounts={accounts} />,
  };

  return (
    <Suspense
      fallback={
        <AppShell title="Accounts">
          {renderSurfaceMessage('Loading accounts...')}
        </AppShell>
      }
    >
      <AppShell title="Accounts">
        <div className="mx-auto w-full max-w-7xl space-y-6">
          {!isAuthenticated && !tenantId && !authLoading && isAuthenticated ? <TenantIdForm onSave={setTenantId} /> : null}

          {showContent ? (
            <>
              <AccountsHero summary={summary} onConnect={() => setIsModalOpen(true)} />
              <AccountSectionTabs activeSection={activeSection} onSelect={setActiveSection} />
            </>
          ) : null}

          {showContent && error ? (
            <RemediationCallout
              tone="danger"
              title="Failed to load accounts"
              description={error}
            >
              <Button variant="secondary" size="sm" onClick={fetchAccounts}>
                Retry
              </Button>
            </RemediationCallout>
          ) : null}

          {showContent && isLoading ? renderSurfaceMessage('Loading accounts...') : null}
          {showContent && !isLoading && !error && accounts.length === 0 ? emptyState : null}
          {showContent && !isLoading && !error && accounts.length > 0 ? contentBySection[activeSection] : null}

          {showContent ? (
            <ConnectAccountModal
              isOpen={isModalOpen}
              onClose={() => {
                setIsModalOpen(false);
                setReconnectAccount(null);
              }}
              onSuccess={fetchAccounts}
              tenantId={tenantId ?? undefined}
              existingAccount={reconnectAccount}
            />
          ) : null}

          {showContent ? (
            <AccountDetailModal
              account={detailAccount}
              isOpen={!!detailAccount}
              onClose={() => setDetailAccount(null)}
              tenantId={tenantId}
              onUpdate={fetchAccounts}
              onReconnect={(account) => {
                setReconnectAccount(account);
                setDetailAccount(null);
                setIsModalOpen(true);
              }}
            />
          ) : null}
        </div>
      </AppShell>
    </Suspense>
  );
}
