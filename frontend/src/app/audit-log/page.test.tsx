import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

import AuditLogPage from '@/app/audit-log/page';
import { useAuth } from '@/contexts/AuthContext';
import { getAuditLog } from '@/lib/api';

vi.mock('@/components/layout', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  getAuditLog: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedGetAuditLog = vi.mocked(getAuditLog);

interface MockAuthUser {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'member';
  onboarding_completed_at: string | null;
  is_saas_admin: boolean;
  phone_number: string | null;
  phone_verified: boolean;
  email_verified: boolean;
}

const adminUser: MockAuthUser = {
  id: 'user-admin',
  email: 'admin@example.com',
  name: 'Tenant Admin',
  role: 'admin',
  onboarding_completed_at: '2026-02-01T00:00:00Z',
  is_saas_admin: false,
  phone_number: null,
  phone_verified: false,
  email_verified: true,
};

function setAuthState(
  state: Partial<{
    isAuthenticated: boolean;
    isLoading: boolean;
    user: MockAuthUser | null;
  }>
) {
  mockedUseAuth.mockReturnValue({
    isAuthenticated: state.isAuthenticated ?? true,
    isLoading: state.isLoading ?? false,
    user: state.user ?? adminUser,
  } as ReturnType<typeof useAuth>);
}

describe('AuditLogPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetAuditLog.mockResolvedValue({
      items: [],
      total: 0,
      limit: 25,
      offset: 0,
    });
  });

  it('fetches audit log as tenant admin with filters and limit/offset pagination', async () => {
    const user = userEvent.setup();
    setAuthState({});
    mockedGetAuditLog.mockResolvedValue({
      items: [
        {
          id: 'event-1',
          tenant_id: 'tenant-1',
          actor_user_id: '123e4567-e89b-12d3-a456-426614174000',
          action: 'aws_account.create',
          resource_type: 'aws_account',
          resource_id: '123456789012',
          timestamp: '2026-02-25T12:00:00Z',
          created_at: '2026-02-25T12:00:00Z',
          payload: null,
        },
      ],
      total: 42,
      limit: 25,
      offset: 0,
    });

    render(<AuditLogPage />);

    await waitFor(() => {
      expect(mockedGetAuditLog).toHaveBeenCalled();
    });
    expect(mockedGetAuditLog.mock.calls[0]?.[0]).toEqual({
      actor_user_id: undefined,
      resource_type: undefined,
      resource_id: undefined,
      from_date: undefined,
      to_date: undefined,
      limit: 25,
      offset: 0,
    });

    await user.type(screen.getByLabelText('Actor User ID'), '123e4567-e89b-12d3-a456-426614174000');
    await user.type(screen.getByLabelText('Resource Type'), 'aws_account');
    await user.type(screen.getByLabelText('Resource ID'), '123456789012');
    await user.type(screen.getByLabelText('From Date'), '2026-02-01');
    await user.type(screen.getByLabelText('To Date'), '2026-02-20');
    await user.click(screen.getByRole('button', { name: 'Apply filters' }));

    await waitFor(() => {
      expect(mockedGetAuditLog).toHaveBeenCalledWith({
        actor_user_id: '123e4567-e89b-12d3-a456-426614174000',
        resource_type: 'aws_account',
        resource_id: '123456789012',
        from_date: '2026-02-01T00:00:00Z',
        to_date: '2026-02-20T23:59:59Z',
        limit: 25,
        offset: 0,
      });
    });

    await user.selectOptions(screen.getByLabelText('Results Per Page'), '50');
    await waitFor(() => {
      expect(mockedGetAuditLog).toHaveBeenCalledWith({
        actor_user_id: '123e4567-e89b-12d3-a456-426614174000',
        resource_type: 'aws_account',
        resource_id: '123456789012',
        from_date: '2026-02-01T00:00:00Z',
        to_date: '2026-02-20T23:59:59Z',
        limit: 50,
        offset: 0,
      });
    });

    await user.selectOptions(screen.getByLabelText('Results Per Page'), '25');
    await user.click(screen.getByRole('button', { name: 'Next page' }));
    await waitFor(() => {
      expect(mockedGetAuditLog).toHaveBeenCalledWith({
        actor_user_id: '123e4567-e89b-12d3-a456-426614174000',
        resource_type: 'aws_account',
        resource_id: '123456789012',
        from_date: '2026-02-01T00:00:00Z',
        to_date: '2026-02-20T23:59:59Z',
        limit: 25,
        offset: 25,
      });
    });

    expect(screen.getByText(/42 events/)).toBeInTheDocument();
  });

  it('shows access denied for non-admin users and never fetches audit logs', async () => {
    setAuthState({
      user: {
        ...adminUser,
        role: 'member',
      },
    });

    render(<AuditLogPage />);

    expect(await screen.findByText('Access denied')).toBeInTheDocument();
    expect(screen.getByText('Only tenant admins can view audit logs.')).toBeInTheDocument();
    expect(mockedGetAuditLog).not.toHaveBeenCalled();
  });

  it('resets filters and reloads unfiltered first page', async () => {
    const user = userEvent.setup();
    setAuthState({});

    render(<AuditLogPage />);

    await waitFor(() => {
      expect(mockedGetAuditLog).toHaveBeenCalledWith({
        actor_user_id: undefined,
        resource_type: undefined,
        resource_id: undefined,
        from_date: undefined,
        to_date: undefined,
        limit: 25,
        offset: 0,
      });
    });

    await user.type(screen.getByLabelText('Actor User ID'), '123e4567-e89b-12d3-a456-426614174000');
    await user.type(screen.getByLabelText('Resource Type'), 'aws_account');
    await user.type(screen.getByLabelText('Resource ID'), '123456789012');
    await user.type(screen.getByLabelText('From Date'), '2026-02-01');
    await user.type(screen.getByLabelText('To Date'), '2026-02-20');
    await user.click(screen.getByRole('button', { name: 'Apply filters' }));

    await waitFor(() => {
      expect(mockedGetAuditLog).toHaveBeenLastCalledWith({
        actor_user_id: '123e4567-e89b-12d3-a456-426614174000',
        resource_type: 'aws_account',
        resource_id: '123456789012',
        from_date: '2026-02-01T00:00:00Z',
        to_date: '2026-02-20T23:59:59Z',
        limit: 25,
        offset: 0,
      });
    });

    await user.click(screen.getByRole('button', { name: 'Reset' }));
    await waitFor(() => {
      expect(mockedGetAuditLog).toHaveBeenLastCalledWith({
        actor_user_id: undefined,
        resource_type: undefined,
        resource_id: undefined,
        from_date: undefined,
        to_date: undefined,
        limit: 25,
        offset: 0,
      });
    });
  });
});
