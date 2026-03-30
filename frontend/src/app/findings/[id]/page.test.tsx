import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

import FindingDetailPage from './page';
import { getFinding } from '@/lib/api';

vi.mock('react', async () => {
  const actual = await vi.importActual<typeof import('react')>('react');
  return {
    ...actual,
    use: <T,>(value: T) => value,
  };
});

vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock('@/components/layout', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/components/help/NeedHelpLink', () => ({
  NeedHelpLink: () => null,
}));

vi.mock('@/components/ui/Button', () => ({
  Button: ({
    children,
    onClick,
    disabled,
  }: {
    children: ReactNode;
    onClick?: () => void;
    disabled?: boolean;
  }) => (
    <button type="button" onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}));

vi.mock('@/components/ui/Badge', () => ({
  Badge: ({ children, title }: { children: ReactNode; title?: string }) => <span title={title}>{children}</span>,
  getSeverityBadgeVariant: () => 'warning',
  getStatusBadgeVariant: () => 'default',
}));

vi.mock('@/components/ui/PendingConfirmationNote', () => ({
  PendingConfirmationNote: ({ message }: { message: string }) => <div>{message}</div>,
}));

vi.mock('@/components/TenantIdForm', () => ({
  TenantIdForm: () => null,
}));

vi.mock('@/components/CreateExceptionModal', () => ({
  CreateExceptionModal: () => null,
}));

vi.mock('@/components/ActionDetailModal', () => ({
  ActionDetailModal: () => null,
}));

vi.mock('@/lib/tenant', () => ({
  useTenantId: () => ({
    tenantId: null,
    setTenantId: vi.fn(),
  }),
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
  }),
}));

vi.mock('@/lib/source', () => ({
  getSourceLabel: () => 'Security Hub',
}));

vi.mock('@/lib/api', () => ({
  getFinding: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}));

const mockedGetFinding = vi.mocked(getFinding);

const baseFinding = {
  id: 'f-1',
  finding_id: 'finding-1',
  tenant_id: 'tenant-1',
  account_id: '123456789012',
  region: 'eu-north-1',
  severity_label: 'INFORMATIONAL',
  severity_normalized: 0,
  status: 'NEW',
  effective_status: 'NEW',
  title: 'Lifecycle configuration missing',
  description: null,
  resource_id: 'arn:aws:s3:::example-bucket',
  resource_type: 'AwsS3Bucket',
  control_id: 'S3.13',
  control_family: {
    source_control_ids: ['S3.13'],
    canonical_control_id: 'S3.11',
    related_control_ids: ['S3.11', 'S3.13'],
    is_mapped: true,
  },
  standard_name: null,
  first_observed_at: null,
  last_observed_at: null,
  updated_at: '2026-03-25T10:00:00Z',
  created_at: '2026-03-25T09:00:00Z',
  updated_at_db: '2026-03-25T10:00:00Z',
  remediation_action_id: 'action-1',
  remediation_action_type: 'pr_only',
  remediation_action_status: 'open',
  remediation_action_account_id: '123456789012',
  remediation_action_region: 'eu-north-1',
  remediation_action_group_id: 'group-1',
  remediation_action_group_status_bucket: 'run_successful_confirmed',
  remediation_action_group_latest_run_status: 'finished',
  status_message: null,
  status_severity: null,
};

describe('Finding detail remediation state', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows explicit confirmed remediation state on the finding detail page', async () => {
    mockedGetFinding.mockResolvedValue(baseFinding);

    render(<FindingDetailPage params={{ id: 'f-1' } as any} />);

    await waitFor(() => {
      expect(mockedGetFinding).toHaveBeenCalledWith('f-1', undefined);
    });

    const badge = (await screen.findByText('Generated and confirmed')).closest('span');
    expect(badge).toHaveAttribute(
      'title',
      'A PR bundle was generated and run successfully, and AWS source-of-truth checks now confirm the finding is resolved.'
    );
  });

  it('shows explicit review-only remediation state on the finding detail page', async () => {
    mockedGetFinding.mockResolvedValue({
      ...baseFinding,
      remediation_action_group_status_bucket: 'run_finished_metadata_only',
    });

    render(<FindingDetailPage params={{ id: 'f-1' } as any} />);

    const badge = (await screen.findByText('Needs review before apply')).closest('span');
    expect(badge).toHaveAttribute(
      'title',
      'The system produced review guidance or bundle artifacts for this item, but did not include runnable automatic changes.'
    );
  });

  it('shows source control and remediation family details on the finding detail page', async () => {
    mockedGetFinding.mockResolvedValue(baseFinding);

    render(<FindingDetailPage params={{ id: 'f-1' } as any} />);

    expect(await screen.findAllByText('S3.13')).toHaveLength(2);
    expect(screen.getByText('Remediation family: S3.11')).toBeInTheDocument();
  });
});
