'use client';

import { Suspense, useEffect } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import { BaselineReportPanel } from '@/components/baseline-report/BaselineReportPanel';
import { NeedHelpLink } from '@/components/help/NeedHelpLink';
import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/contexts/AuthContext';
import {
  DashboardHero,
  DashboardTabButton,
  DashboardTabList,
  SectionTitleExplainer,
  remediationInsetClass,
} from '@/components/ui/remediation-surface';
import { GovernanceSettingsTab } from './GovernanceSettingsTab';
import { IntegrationsSettingsTab } from './IntegrationsSettingsTab';
import { NotificationsSettingsTab } from './NotificationsSettingsTab';
import { OrganizationSettingsTab } from './OrganizationSettingsTab';
import { ProfileTab } from './ProfileTab';
import { RemediationDefaultsTab } from './RemediationDefaultsTab';
import {
  SETTINGS_TAB_ITEMS,
  buildSettingsTabHref,
  isLegacyExportsSettingsTab,
  normalizeSettingsTab,
} from './settings-tabs';
import { TeamSettingsTab } from './TeamSettingsTab';

function SettingsContent() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const requestedTab = searchParams.get('tab');
  const legacyExportsTabRequested = isLegacyExportsSettingsTab(requestedTab);
  const activeTab = normalizeSettingsTab(requestedTab);
  const helpFrom = buildSettingsTabHref(activeTab);

  useEffect(() => {
    if (legacyExportsTabRequested) {
      router.replace('/exports', { scroll: false });
      return;
    }
    if (!requestedTab) return;
    if (requestedTab === activeTab) return;
    router.replace(buildSettingsTabHref(activeTab), { scroll: false });
  }, [activeTab, legacyExportsTabRequested, requestedTab, router]);

  if (!authLoading && !isAuthenticated) {
    return (
      <AppShell title="Settings">
        <div className="mx-auto w-full max-w-4xl">
          <div className={remediationInsetClass('default', 'p-8 text-center')}>
            <p className="mb-4 text-muted">Please sign in to view settings.</p>
            <Button onClick={() => {
              window.location.href = '/login';
            }}>
              Sign In
            </Button>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Settings">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        {legacyExportsTabRequested ? null : (
          <DashboardHero
            eyebrow="Workspace controls"
            title="Settings"
            titleExplainer={<SectionTitleExplainer conceptId="settings_surface" context="settings" label="Settings" />}
            description="Manage account security, team access, integrations, governance, remediation defaults, and reporting from one consistent operator surface."
            action={<NeedHelpLink from={helpFrom} label="Need help with settings?" variant="secondary" />}
            tone="accent"
          >
            <DashboardTabList role="tablist">
              {SETTINGS_TAB_ITEMS.map((tab) => (
                <DashboardTabButton
                  key={tab.value}
                  role="tab"
                  active={activeTab === tab.value}
                  aria-selected={activeTab === tab.value}
                  aria-controls={tab.panelId}
                  onClick={() => {
                    const nextHref = tab.value === activeTab
                      ? `${pathname}${searchParams.toString() ? `?${searchParams.toString()}` : ''}`
                      : buildSettingsTabHref(tab.value);
                    router.replace(nextHref, { scroll: false });
                  }}
                >
                  {tab.label}
                </DashboardTabButton>
              ))}
            </DashboardTabList>
          </DashboardHero>
        )}

        {!legacyExportsTabRequested && activeTab === 'account' ? (
          <div id="settings-panel-account" role="tabpanel" tabIndex={0} className="space-y-6">
            <ProfileTab />
          </div>
        ) : null}

        {!legacyExportsTabRequested && activeTab === 'team' ? <TeamSettingsTab /> : null}
        {!legacyExportsTabRequested && activeTab === 'organization' ? <OrganizationSettingsTab /> : null}
        {!legacyExportsTabRequested && activeTab === 'notifications' ? <NotificationsSettingsTab /> : null}
        {!legacyExportsTabRequested && activeTab === 'integrations' ? <IntegrationsSettingsTab /> : null}
        {!legacyExportsTabRequested && activeTab === 'governance' ? <GovernanceSettingsTab /> : null}
        {!legacyExportsTabRequested && activeTab === 'remediation-defaults' ? <RemediationDefaultsTab /> : null}
        {!legacyExportsTabRequested && activeTab === 'baseline-report' ? (
          <div id="settings-panel-baseline-report" role="tabpanel" tabIndex={0}>
            <BaselineReportPanel />
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}

export default function SettingsPage() {
  return (
    <Suspense
      fallback={(
        <AppShell title="Settings">
          <div className="flex items-center justify-center p-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--accent)] border-t-transparent" />
          </div>
        </AppShell>
      )}
    >
      <SettingsContent />
    </Suspense>
  );
}
