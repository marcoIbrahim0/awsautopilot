import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import FindingsPage from './page';
import { getAccounts, getFindingGroups, getFindings, getScopeMeta, type FindingGroup } from '@/lib/api';

vi.mock('motion/react', () => ({
  motion: {
    div: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () =>
    new URLSearchParams(
      'resource_id=arn%3Aaws%3Aconfig%3Aus-east-1%3A696505809372%3Aconfig-rule%2Focypheris-p2-config-fresh-kev'
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
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
    [key: string]: unknown;
  }) => (
    <button type="button" onClick={onClick} disabled={disabled} {...props}>
      {children}
    </button>
  ),
}));

vi.mock('@/components/ui/Badge', () => ({
  Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

vi.mock('@/components/ui/SelectDropdown', () => ({
  SelectDropdown: () => null,
}));

vi.mock('@/components/ui/placeholders-and-vanish-input', () => ({
  PlaceholdersAndVanishInput: () => null,
}));

vi.mock('@/components/ui/BackgroundJobsProgressBanner', () => ({
  BackgroundJobsProgressBanner: () => null,
}));

vi.mock('@/components/TenantIdForm', () => ({
  TenantIdForm: () => null,
}));

vi.mock('@/components/ActionDetailModal', () => ({
  ActionDetailModal: () => null,
}));

vi.mock('./GroupedFindingsView', () => ({
  GroupedFindingsView: ({ groups }: { groups: Array<{ group_key: string; rule_title: string }> }) => (
    <div data-testid="grouped-view">
      {groups.map((group) => (
        <div key={group.group_key}>{group.rule_title}</div>
      ))}
    </div>
  ),
}));

vi.mock('./FindingCard', () => ({
  FindingCard: () => null,
}));

vi.mock('./FindingGroupCard', () => ({
  FindingGroupCard: () => null,
}));

vi.mock('./GroupingControlBar', () => ({
  GroupingControlBar: () => null,
}));

vi.mock('./SeverityTabs', () => ({
  SeverityTabs: () => null,
}));

vi.mock('./Pagination', () => ({
  Pagination: () => null,
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    user: { id: 'user-1', role: 'admin' },
  }),
}));

vi.mock('@/lib/tenant', () => ({
  useTenantId: () => ({
    tenantId: 'tenant-local',
    setTenantId: vi.fn(),
  }),
}));

const addJob = vi.fn(() => 'job-1');
const updateJob = vi.fn();
const completeJob = vi.fn();
const timeoutJob = vi.fn();
const failJob = vi.fn();

vi.mock('@/contexts/BackgroundJobsContext', () => ({
  useBackgroundJobs: () => ({
    jobs: [],
    addJob,
    updateJob,
    completeJob,
    timeoutJob,
    failJob,
  }),
}));

vi.mock('@/lib/source', () => ({
  getSourceLabel: (value: string) => value,
  SOURCE_FILTER_VALUES: [{ value: '', label: 'All sources' }],
}));

vi.mock('@/lib/errorLogger', () => ({
  logError: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  getFindings: vi.fn(),
  getActions: vi.fn(),
  getAccounts: vi.fn(),
  triggerComputeActions: vi.fn(),
  triggerIngest: vi.fn(),
  getFindingGroups: vi.fn(),
  getScopeMeta: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}));

const mockedGetFindings = vi.mocked(getFindings);
const mockedGetFindingGroups = vi.mocked(getFindingGroups);
const mockedGetAccounts = vi.mocked(getAccounts);
const mockedGetScopeMeta = vi.mocked(getScopeMeta);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const filteredGroup: FindingGroup = {
  group_key: 'Config.1|AwsConfigRule|696505809372|us-east-1',
  control_id: 'Config.1',
  rule_title: 'Filtered trusted threat intel group',
  resource_type: 'AwsConfigRule',
  finding_count: 1,
  severity_distribution: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 1, INFORMATIONAL: 0 },
  account_ids: ['696505809372'],
  regions: ['us-east-1'],
  remediation_action_id: '73097c11-174c-4597-85a2-9af793842e8d',
  remediation_action_type: 'aws_config_enabled',
  remediation_action_status: 'resolved',
  risk_acknowledged: false,
  risk_acknowledged_count: 0,
};

const staleGroup: FindingGroup = {
  ...filteredGroup,
  rule_title: 'Stale unfiltered group',
  remediation_action_id: '7d51a23a-9af2-4a82-ae75-67561c01cf8e',
  remediation_action_status: 'open',
  risk_acknowledged: false,
  risk_acknowledged_count: 0,
};

const readyGroup: FindingGroup = {
  ...filteredGroup,
  group_key: 'Config.1|ready',
  rule_title: 'Ready to generate group',
  remediation_action_id: 'action-ready',
  remediation_action_status: 'open',
  remediation_action_group_status_bucket: 'not_run_yet',
};

const reviewGroup: FindingGroup = {
  ...filteredGroup,
  group_key: 'Config.1|review',
  rule_title: 'Needs review group',
  remediation_action_id: 'action-review',
  remediation_action_status: 'open',
  remediation_action_group_status_bucket: 'run_finished_metadata_only',
};

const noFixGroup: FindingGroup = {
  ...filteredGroup,
  group_key: 'Config.1|no-fix',
  rule_title: 'No runnable fix group',
  remediation_action_id: null,
  remediation_action_status: null,
  remediation_action_group_status_bucket: null,
  remediation_visibility_reason: 'managed_on_account_scope',
};

describe('FindingsPageContent grouped refresh behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetFindings.mockResolvedValue({
      items: [
        {
          id: 'finding-1',
          finding_id: 'finding-1',
          tenant_id: 'tenant-local',
          account_id: '696505809372',
          region: 'us-east-1',
          severity_label: 'LOW',
          severity_normalized: 0.25,
          status: 'RESOLVED',
          effective_status: 'RESOLVED',
          title: 'Synthetic Config finding with trusted threat intel',
          description: null,
          resource_id: 'arn:aws:config:us-east-1:696505809372:config-rule/ocypheris-p2-config-fresh-kev',
          resource_type: 'AwsConfigRule',
          control_id: 'Config.1',
          standard_name: null,
          first_observed_at: null,
          last_observed_at: null,
          updated_at: null,
          created_at: '2026-03-12T00:00:00Z',
          updated_at_db: '2026-03-12T00:00:00Z',
          source: 'security_hub',
          risk_acknowledged: false,
          remediation_action_id: '73097c11-174c-4597-85a2-9af793842e8d',
          remediation_action_type: 'aws_config_enabled',
          remediation_action_status: 'resolved',
          remediation_action_account_id: '696505809372',
          remediation_action_region: 'us-east-1',
        },
      ],
      total: 1,
    } as never);
    mockedGetAccounts.mockResolvedValue([]);
    mockedGetScopeMeta.mockResolvedValue({
      only_in_scope_controls: false,
      in_scope_controls_count: 0,
      disabled_sources: [],
    });
  });

  it('defaults SaaS findings requests to open statuses only', async () => {
    mockedGetFindingGroups.mockResolvedValue({ items: [filteredGroup], total: 1 });

    render(<FindingsPage />);

    await waitFor(() => {
      expect(mockedGetFindings).toHaveBeenCalledWith(
        expect.objectContaining({
          status: 'NEW,NOTIFIED',
        }),
        'tenant-local'
      );
      expect(mockedGetFindingGroups).toHaveBeenCalledWith(
        expect.objectContaining({
          status: 'NEW,NOTIFIED',
        }),
        'tenant-local'
      );
    });
  });

  it('ignores stale grouped responses that resolve after a filtered request', async () => {
    const firstRequest = deferred<{ items: typeof staleGroup[]; total: number }>();
    const secondRequest = deferred<{ items: typeof filteredGroup[]; total: number }>();

    mockedGetFindingGroups.mockImplementation((filters) => {
      if (filters?.resource_id) return secondRequest.promise as never;
      return firstRequest.promise as never;
    });

    render(<FindingsPage />);

    await waitFor(() => expect(mockedGetFindingGroups).toHaveBeenCalledTimes(2));

    await act(async () => {
      secondRequest.resolve({ items: [filteredGroup], total: 1 });
      await secondRequest.promise;
    });

    expect(await screen.findByText('Filtered trusted threat intel group')).toBeInTheDocument();

    await act(async () => {
      firstRequest.resolve({ items: [staleGroup], total: 1 });
      await firstRequest.promise;
    });

    await waitFor(() => {
      expect(screen.getByText('Filtered trusted threat intel group')).toBeInTheDocument();
      expect(screen.queryByText('Stale unfiltered group')).not.toBeInTheDocument();
    });
  });

  it('refreshes grouped cards when grouped mode is active', async () => {
    const user = userEvent.setup();
    mockedGetFindingGroups.mockResolvedValue({ items: [filteredGroup], total: 1 });

    render(<FindingsPage />);

    expect(await screen.findByText('Filtered trusted threat intel group')).toBeInTheDocument();
    const initialCalls = mockedGetFindingGroups.mock.calls.length;

    await user.click(screen.getByRole('button', { name: 'Refresh' }));

    await waitFor(() => {
      expect(mockedGetFindingGroups.mock.calls.length).toBeGreaterThan(initialCalls);
    });
  });

  it('renders remediation quick filters and filters grouped results locally', async () => {
    const user = userEvent.setup();
    mockedGetFindingGroups.mockResolvedValue({
      items: [readyGroup, reviewGroup, noFixGroup],
      total: 3,
    });

    render(<FindingsPage />);

    expect(await screen.findByText('Ready to generate group')).toBeInTheDocument();
    expect(screen.getByText('Needs review group')).toBeInTheDocument();
    expect(screen.getByText('No runnable fix group')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ready to generate (1)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Needs review before apply (1)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'No runnable fix here (1)' })).toBeInTheDocument();

    const initialCalls = mockedGetFindingGroups.mock.calls.length;
    await user.click(screen.getByRole('button', { name: 'Needs review before apply (1)' }));

    expect(screen.queryByText('Ready to generate group')).not.toBeInTheDocument();
    expect(screen.getByText('Needs review group')).toBeInTheDocument();
    expect(screen.queryByText('No runnable fix group')).not.toBeInTheDocument();
    expect(screen.getByText('Remediation: Needs review before apply')).toBeInTheDocument();
    expect(mockedGetFindingGroups.mock.calls.length).toBe(initialCalls);
  });
});
