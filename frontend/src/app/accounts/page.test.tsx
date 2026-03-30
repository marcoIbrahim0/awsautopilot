import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

import AccountsPage from './page';
import { getAccounts } from '@/lib/api';

vi.mock('next/link', () => ({
  default: ({
    children,
    href,
  }: {
    children: ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

vi.mock('@/components/layout', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/components/TenantIdForm', () => ({
  TenantIdForm: () => null,
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

vi.mock('@/components/ui/Badge', () => ({
  Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
  getStatusBadgeVariant: () => 'default',
}));

vi.mock('@/components/ui/remediation-surface', () => ({
  REMEDIATION_EYEBROW_CLASS: 'eyebrow',
  RemediationCallout: ({
    children,
    title,
    description,
  }: {
    children?: ReactNode;
    title?: ReactNode;
    description?: ReactNode;
  }) => (
    <section>
      {title ? <h2>{title}</h2> : null}
      {description ? <p>{description}</p> : null}
      {children}
    </section>
  ),
  RemediationPanel: ({ children }: { children: ReactNode }) => <section>{children}</section>,
  RemediationSection: ({
    children,
    title,
    description,
    action,
  }: {
    children: ReactNode;
    title?: ReactNode;
    description?: ReactNode;
    action?: ReactNode;
  }) => (
    <section>
      {title ? <h2>{title}</h2> : null}
      {description ? <p>{description}</p> : null}
      {action}
      {children}
    </section>
  ),
  RemediationStatCard: ({
    label,
    value,
    labelExplainer,
    detail,
  }: {
    label: ReactNode;
    value: ReactNode;
    labelExplainer?: ReactNode;
    detail?: ReactNode;
  }) => (
    <div>
      <span>{label}</span>
      {labelExplainer}
      <strong>{value}</strong>
      {detail ? <p>{detail}</p> : null}
    </div>
  ),
  SectionTitleExplainer: ({ label }: { label?: string }) => (
    <button aria-label="Show contextual help" title={`Show help for ${label ?? 'section'}`}>i</button>
  ),
  remediationInsetClass: () => '',
  remediationPanelClass: () => '',
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
  }),
}));

vi.mock('@/lib/tenant', () => ({
  useTenantId: () => ({
    tenantId: null,
    setTenantId: vi.fn(),
  }),
}));

vi.mock('./ConnectAccountModal', () => ({
  ConnectAccountModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div>Connect modal open</div> : null,
}));

vi.mock('./AccountDetailModal', () => ({
  AccountDetailModal: ({ account }: { account: { account_id: string } | null }) =>
    account ? <div>Detail modal for {account.account_id}</div> : null,
}));

vi.mock('./AccountRowActions', () => ({
  AccountRowActions: () => <div>Account row actions</div>,
}));

vi.mock('@/lib/api', () => ({
  getAccounts: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}));

const mockedGetAccounts = vi.mocked(getAccounts);

describe('AccountsPage', () => {
  beforeEach(() => {
    mockedGetAccounts.mockReset();
    mockedGetAccounts.mockResolvedValue([
      {
        id: 'acct-1',
        account_id: '123456789012',
        role_read_arn: 'arn:aws:iam::123456789012:role/ReadRole',
        role_write_arn: null,
        regions: ['us-east-1', 'eu-west-1'],
        status: 'validated',
        last_validated_at: '2026-03-13T12:00:00Z',
        created_at: '2026-03-10T12:00:00Z',
        updated_at: '2026-03-13T12:00:00Z',
      },
      {
        id: 'acct-2',
        account_id: '210987654321',
        role_read_arn: 'arn:aws:iam::210987654321:role/ReadRole',
        role_write_arn: 'arn:aws:iam::210987654321:role/WriteRole',
        regions: ['us-east-1'],
        status: 'pending',
        last_validated_at: null,
        created_at: '2026-03-11T12:00:00Z',
        updated_at: '2026-03-13T12:00:00Z',
      },
    ] as never);
  });

  it('renders the dashboard-style account hub and switches sections', async () => {
    const user = userEvent.setup();
    const { container } = render(<AccountsPage />);

    expect(await screen.findByRole('heading', { name: 'Connected AWS accounts' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Show contextual help' }).length).toBeGreaterThan(0);
    expect(screen.getByText('Validate once in onboarding, operate continuously from Accounts.')).toBeInTheDocument();
    expect(screen.getByText('Monitored regions')).toBeInTheDocument();
    expect(screen.queryByText(/WriteRole/i)).not.toBeInTheDocument();
    expect(container.querySelector('a button, button a')).toBeNull();

    expect(await screen.findByRole('heading', { name: 'Connection state and quick account actions' })).toBeInTheDocument();
    expect(screen.getByText('123456789012')).toBeInTheDocument();
    expect(screen.getAllByText('Account row actions')).toHaveLength(2);

    await user.click(screen.getByRole('tab', { name: 'Roles & permissions ReadRole posture and monitored-region scope across connected accounts.' }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'ReadRole posture' })).toBeInTheDocument();
    });
    expect(screen.getByText('Review the connected ReadRole configuration for each account and use account details for reconnect or lifecycle actions.')).toBeInTheDocument();
    expect(screen.getAllByText('Review account')).toHaveLength(2);
  });
});
