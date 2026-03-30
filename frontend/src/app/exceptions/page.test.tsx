import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import ExceptionsPage from './page';
import { applyFindingGroupAction, getExceptions } from '@/lib/api';

const replace = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  usePathname: () => '/exceptions',
  useSearchParams: () =>
    new URLSearchParams(
      'group_action=suppress&group_key=opaque-s3-bucket-group&control_id=S3.1&resource_type=AWS%3A%3AS3%3A%3ABucket&account_id=123456789012&region=us-east-1&severity=HIGH&status=NEW'
    ),
}));

vi.mock('@/components/layout', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/components/ui/Button', () => ({
  Button: ({
    children,
    onClick,
    disabled,
    isLoading,
    leftIcon,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
    isLoading?: boolean;
    leftIcon?: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <button type="button" onClick={onClick} disabled={disabled} {...props}>
      {leftIcon}
      {isLoading ? 'Loading...' : children}
    </button>
  ),
}));

vi.mock('@/components/ui/Badge', () => ({
  Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

vi.mock('@/components/ui/Modal', () => ({
  Modal: ({
    isOpen,
    children,
    title,
  }: {
    isOpen: boolean;
    children: React.ReactNode;
    title: string;
  }) => (isOpen ? <div role="dialog" aria-label={title}>{children}</div> : null),
}));

vi.mock('@/components/ui/SelectDropdown', () => ({
  SelectDropdown: () => null,
}));

vi.mock('@/components/ui/Input', () => ({
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock('@/components/TenantIdForm', () => ({
  TenantIdForm: () => null,
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
  }),
}));

vi.mock('@/lib/tenant', () => ({
  useTenantId: () => ({
    tenantId: 'tenant-local',
    setTenantId: vi.fn(),
  }),
}));

vi.mock('@/lib/api', () => ({
  getExceptions: vi.fn(),
  revokeException: vi.fn(),
  applyFindingGroupAction: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}));

const mockedGetExceptions = vi.mocked(getExceptions);
const mockedApplyFindingGroupAction = vi.mocked(applyFindingGroupAction);

describe('ExceptionsPage grouped suppress flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetExceptions.mockResolvedValue({ items: [], total: 0 });
  });

  it('auto-opens grouped suppress flow from search params and submits through the grouped action API', async () => {
    const user = userEvent.setup();
    mockedApplyFindingGroupAction.mockResolvedValue({
      action: 'suppress',
      group_key: 'opaque-s3-bucket-group',
      matched_findings: 2,
      acknowledged_findings: 0,
      status_updates: 0,
      exceptions_created: 2,
      exceptions_updated: 0,
    });

    render(<ExceptionsPage />);

    expect(await screen.findByRole('dialog', { name: 'Suppress Group' })).toBeInTheDocument();
    expect(screen.getAllByText('S3.1 · AWS::S3::Bucket · 123456789012 · us-east-1').length).toBeGreaterThan(0);

    await user.type(screen.getByLabelText('Reason'), 'Grouped suppression approved for planned maintenance window.');
    await user.type(screen.getByLabelText('Ticket Link'), 'https://jira.example.com/SEC-123');

    await user.click(screen.getByRole('button', { name: 'Apply Suppression' }));

    await waitFor(() => {
      expect(mockedApplyFindingGroupAction).toHaveBeenCalledWith({
        action: 'suppress',
        group_key: 'opaque-s3-bucket-group',
        reason: 'Grouped suppression approved for planned maintenance window.',
        ticket_link: 'https://jira.example.com/SEC-123',
        expires_at: expect.any(String),
        account_id: '123456789012',
        region: 'us-east-1',
        severity: 'HIGH',
        source: undefined,
        status: 'NEW',
        control_id: 'S3.1',
        resource_id: undefined,
      });
    });

    expect(replace).toHaveBeenCalledWith('/exceptions');
  });
});
