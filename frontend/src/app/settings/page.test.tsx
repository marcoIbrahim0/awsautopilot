import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SettingsPage from './page';

vi.mock('@/components/ui/ExplainerHint', () => ({
  ExplainerHint: ({ label }: { label?: string }) => <button aria-label="Show contextual help" title={`Show help for ${label ?? 'item'}`}>i</button>,
}));

const replace = vi.fn();
let currentSearch = '';

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(currentSearch),
  useRouter: () => ({ replace }),
  usePathname: () => '/settings',
}));

vi.mock('@/components/layout', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/components/ui/Button', () => ({
  buttonClassName: () => '',
  Button: ({
    children,
    onClick,
    disabled,
    type = 'button',
  }: {
    children: ReactNode;
    onClick?: () => void;
    disabled?: boolean;
    type?: 'button' | 'submit' | 'reset';
  }) => (
    <button type={type} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
  }),
}));

vi.mock('./ProfileTab', () => ({
  ProfileTab: () => <div>Account tab content</div>,
}));

vi.mock('./TeamSettingsTab', () => ({
  TeamSettingsTab: () => <div>Team tab content</div>,
}));

vi.mock('./OrganizationSettingsTab', () => ({
  OrganizationSettingsTab: () => <div>Organization tab content</div>,
}));

vi.mock('./NotificationsSettingsTab', () => ({
  NotificationsSettingsTab: () => <div>Notifications tab content</div>,
}));

vi.mock('./IntegrationsSettingsTab', () => ({
  IntegrationsSettingsTab: () => <div>Integrations tab content</div>,
}));

vi.mock('./GovernanceSettingsTab', () => ({
  GovernanceSettingsTab: () => <div>Governance tab content</div>,
}));

vi.mock('./RemediationDefaultsTab', () => ({
  RemediationDefaultsTab: () => <div>Remediation defaults tab content</div>,
}));

vi.mock('@/components/baseline-report/BaselineReportPanel', () => ({
  BaselineReportPanel: () => <div>Baseline report tab content</div>,
}));

describe('SettingsPage', () => {
  beforeEach(() => {
    currentSearch = '';
    replace.mockReset();
  });

  it('renders the requested integrations tab from the URL query param', async () => {
    currentSearch = 'tab=integrations';

    render(<SettingsPage />);

    expect(await screen.findByText('Integrations tab content')).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Exports & Compliance' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Show contextual help' }).length).toBeGreaterThan(0);
    expect(replace).not.toHaveBeenCalled();
  });

  it('redirects legacy export tabs to the top-level exports page', async () => {
    currentSearch = 'tab=evidence-export';

    render(<SettingsPage />);

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith('/exports', { scroll: false });
    });
  });

  it('updates the URL when a different settings tab is selected', async () => {
    const user = userEvent.setup();

    render(<SettingsPage />);

    expect(await screen.findByText('Account tab content')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Baseline Report' }));

    expect(replace).toHaveBeenCalledWith('/settings?tab=baseline-report', { scroll: false });
  });
});
