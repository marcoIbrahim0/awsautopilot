import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

import ActionGroupDetailPage from './page';
import {
  createActionGroupBundleRun,
  getActionGroup,
  getActionGroupRuns,
  getRemediationOptions,
  isApiError,
} from '@/lib/api';

const replace = vi.fn();
const router = { replace };
let searchParamValue = 'group_id=group-1';
let searchParams = new URLSearchParams(searchParamValue);

vi.mock('next/navigation', () => ({
  useRouter: () => router,
  useSearchParams: () => searchParams,
}));

vi.mock('@/components/layout', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
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
  buttonClassName: () => 'mock-button-class',
}));

vi.mock('@/components/ui/Badge', () => ({
  Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock('@/components/ui/BackgroundJobsProgressBanner', () => ({
  BackgroundJobsProgressBanner: () => null,
}));

vi.mock('@/components/TenantIdForm', () => ({
  TenantIdForm: () => null,
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    user: { id: 'user-1', role: 'admin' },
  }),
}));

vi.mock('@/lib/tenant', () => ({
  useTenantId: () => ({
    tenantId: null,
    setTenantId: vi.fn(),
  }),
}));

vi.mock('@/lib/pr-bundle-download', () => ({
  downloadPrBundleZip: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  createActionGroupBundleRun: vi.fn(),
  getActionGroup: vi.fn(),
  getActionGroupRuns: vi.fn(),
  getActionGroups: vi.fn(),
  getRemediationOptions: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
  isApiError: vi.fn(
    (error: unknown) =>
      typeof error === 'object' && error !== null && 'error' in error && 'status' in error
  ),
  getRemediationRun: vi.fn(),
}));

const mockedGetActionGroup = vi.mocked(getActionGroup);
const mockedGetActionGroupRuns = vi.mocked(getActionGroupRuns);
const mockedGetRemediationOptions = vi.mocked(getRemediationOptions);
const mockedCreateActionGroupBundleRun = vi.mocked(createActionGroupBundleRun);
const mockedIsApiError = vi.mocked(isApiError);

function makeActionGroupDetail() {
  return {
    id: 'group-1',
    tenant_id: 'tenant-1',
    group_key: 'tenant-1|aws_config_enabled|123456789012|eu-north-1',
    action_type: 'aws_config_enabled',
    account_id: '123456789012',
    region: 'eu-north-1',
    created_at: '2026-03-19T00:00:00Z',
    updated_at: '2026-03-19T00:00:00Z',
    metadata: {},
    counters: {
      run_successful: 1,
      run_not_successful: 0,
      metadata_only: 1,
      not_run_yet: 1,
      total_actions: 3,
    },
    can_generate_bundle: true,
    blocked_reason: null,
    blocked_detail: null,
    blocked_by_run_id: null,
    members: [
      {
        action_id: 'action-1',
        title: 'Remove unrestricted security group rule',
        control_id: 'Config.1',
        resource_id: 'resource-1',
        action_status: 'open',
        priority: 32,
        assigned_at: null,
        status_bucket: 'run_successful_needs_followup',
        last_attempt_at: '2026-03-19T01:00:00Z',
        last_confirmed_at: '2026-03-19T01:10:00Z',
        last_confirmation_source: 'security_hub',
        latest_run: {
          id: 'run-1',
          status: 'finished',
          started_at: '2026-03-19T01:00:00Z',
          finished_at: '2026-03-19T01:05:00Z',
        },
        pending_confirmation: true,
        pending_confirmation_started_at: '2026-03-19T01:05:00Z',
        pending_confirmation_deadline_at: '2026-03-19T13:05:00Z',
        pending_confirmation_message:
          'The fix was applied successfully. Restricted access was added, but unrestricted public access is still present. Remove the unrestricted rule to resolve this finding.',
        pending_confirmation_severity: 'warning',
        status_message:
          'The fix was applied successfully. Restricted access was added, but unrestricted public access is still present. Remove the unrestricted rule to resolve this finding.',
        status_severity: 'warning',
        followup_kind: 'unrestricted_public_access_retained',
      },
      {
        action_id: 'action-2',
        title: 'Keep centralized bucket review-only',
        control_id: 'Config.1',
        resource_id: 'resource-2',
        action_status: 'open',
        priority: 28,
        assigned_at: null,
        status_bucket: 'run_finished_metadata_only',
        last_attempt_at: '2026-03-19T01:00:00Z',
        last_confirmed_at: null,
        last_confirmation_source: null,
        latest_run: {
          id: 'run-1',
          status: 'finished',
          started_at: '2026-03-19T01:00:00Z',
          finished_at: '2026-03-19T01:05:00Z',
        },
        pending_confirmation: false,
        pending_confirmation_started_at: null,
        pending_confirmation_deadline_at: null,
        pending_confirmation_message: null,
        pending_confirmation_severity: null,
        status_message: null,
        status_severity: null,
        followup_kind: null,
      },
      {
        action_id: 'action-3',
        title: 'Historical blocked action',
        control_id: 'Config.1',
        resource_id: 'resource-3',
        action_status: 'open',
        priority: 12,
        assigned_at: null,
        status_bucket: 'not_run_yet',
        last_attempt_at: null,
        last_confirmed_at: null,
        last_confirmation_source: null,
        latest_run: {
          id: null,
          status: null,
          started_at: null,
          finished_at: null,
        },
        pending_confirmation: false,
        pending_confirmation_started_at: null,
        pending_confirmation_deadline_at: null,
        pending_confirmation_message: null,
        pending_confirmation_severity: null,
        status_message: null,
        status_severity: null,
        followup_kind: null,
      },
    ],
  };
}

describe('ActionGroupDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedIsApiError.mockImplementation(
      (error: unknown): error is { error: string; status: number; detail?: unknown } =>
        typeof error === 'object' && error !== null && 'error' in error && 'status' in error
    );
    searchParamValue = 'group_id=group-1';
    searchParams = new URLSearchParams(searchParamValue);
    mockedGetActionGroup.mockResolvedValue(makeActionGroupDetail() as never);
    mockedGetActionGroupRuns.mockResolvedValue({
      items: [
        {
          id: 'run-1',
          remediation_run_id: 'rem-run-1',
          initiated_by_user_id: 'user-1',
          mode: 'download_bundle',
          status: 'finished',
          started_at: '2026-03-19T01:00:00Z',
          finished_at: '2026-03-19T01:05:00Z',
          reporting_source: 'bundle_callback',
          created_at: '2026-03-19T01:00:00Z',
          updated_at: '2026-03-19T01:05:00Z',
          shared_execution_results: [
            {
              folder: 'executable/actions/00-shared-01-security-autopilot-access-logs',
              kind: 's3_access_logging_destination_setup',
              execution_status: 'failed',
              execution_error_code: 'bucket_already_owned',
              execution_error_message: 'Shared destination setup failed.',
              details: { destination_bucket_name: 'security-autopilot-access-logs-123456789012' },
            },
          ],
          results: [
            {
              action_id: 'action-1',
              execution_status: 'success',
              execution_error_code: null,
              execution_error_message: null,
              result_type: 'executable',
              support_tier: null,
              reason: null,
              blocked_reasons: [],
              decision_rationale: null,
              preservation_summary: {},
              strategy_inputs: {},
              execution_started_at: '2026-03-19T01:00:00Z',
              execution_finished_at: '2026-03-19T01:03:00Z',
            },
            {
              action_id: 'action-2',
              execution_status: 'unknown',
              execution_error_code: null,
              execution_error_message: null,
              result_type: 'non_executable',
              support_tier: 'review_required_bundle',
              reason: 'review_required_metadata_only',
              blocked_reasons: ['needs approval'],
              decision_rationale: 'No automatic changes were included because the system could not prove this branch was safe.',
              preservation_summary: { destination_bucket_name: 'security-autopilot-access-logs-123456789012' },
              strategy_inputs: { log_bucket_name: 'security-autopilot-access-logs-123456789012' },
              execution_started_at: null,
              execution_finished_at: null,
            },
          ],
        },
        {
          id: 'run-0',
          remediation_run_id: 'rem-run-0',
          initiated_by_user_id: 'user-1',
          mode: 'download_bundle',
          status: 'failed',
          started_at: '2026-03-18T01:00:00Z',
          finished_at: '2026-03-18T01:05:00Z',
          reporting_source: 'bundle_callback',
          created_at: '2026-03-18T01:00:00Z',
          updated_at: '2026-03-18T01:05:00Z',
          shared_execution_results: [],
          results: [
            {
              action_id: 'action-3',
              execution_status: 'failed',
              execution_error_code: 'invalid_strategy_inputs',
              execution_error_message: 'Previous generation failed.',
              result_type: 'executable',
              support_tier: null,
              reason: null,
              blocked_reasons: [],
              decision_rationale: null,
              preservation_summary: {},
              strategy_inputs: {},
              execution_started_at: '2026-03-18T01:00:00Z',
              execution_finished_at: '2026-03-18T01:02:00Z',
            },
          ],
        },
      ],
      total: 2,
    } as never);
    mockedGetRemediationOptions.mockResolvedValue({
      action_id: 'action-1',
      action_type: 'aws_config_enabled',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'config_enable_account_local_delivery',
          label: 'Enable AWS Config locally',
          mode: 'pr_only',
          risk_level: 'low',
          recommended: true,
          requires_inputs: false,
          input_schema: { fields: [] },
          dependency_checks: [],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
        },
      ],
      recommendation: {
        recommended_mode: 'pr_only',
        recommended_strategy_id: 'config_enable_account_local_delivery',
        rationale: [],
      },
      manual_high_risk: false,
      pre_execution_notice: null,
      runbook_url: null,
      manual_workflow: null,
    } as never);
    mockedCreateActionGroupBundleRun.mockResolvedValue({
      group_run_id: 'group-run-2',
      remediation_run_id: 'rem-run-2',
      reporting_token: 'token',
      reporting_callback_url: 'https://api.example.com/api/internal/group-runs/report',
      status: 'queued',
    } as never);
  });

  it('renders the follow-up section and collapses older generation outcomes by default', async () => {
    render(<ActionGroupDetailPage />);

    await waitFor(() => {
      expect(mockedGetActionGroup).toHaveBeenCalledWith('group-1', undefined);
      expect(mockedGetActionGroupRuns).toHaveBeenCalledWith('group-1', { limit: 100, offset: 0 }, undefined);
    });

    expect(screen.getByRole('link', { name: 'Back to Findings' })).toHaveAttribute('href', '/findings');
    expect(screen.queryByText('Generation not successful')).not.toBeInTheDocument();
    expect(screen.queryByText('Not generated yet')).not.toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { level: 2, name: /Generated and needs follow-up/i })
    ).toBeInTheDocument();
    expect(screen.getAllByText('Remove unrestricted security group rule')).toHaveLength(2);
    expect(
      screen.getAllByText(
        'The fix was applied successfully. Restricted access was added, but unrestricted public access is still present. Remove the unrestricted rule to resolve this finding.'
      )
    ).toHaveLength(2);
    expect(screen.getByRole('link', { name: 'Open action and refresh state' })).toHaveAttribute(
      'href',
      '/actions/action-1'
    );

    expect(
      screen.getAllByText('1 succeeded · 0 failed · 1 executable · 1 needs review/manual follow-up').length
    ).toBeGreaterThan(0);
    expect(screen.getAllByText('Needs review before apply').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Keep centralized bucket review-only')).toHaveLength(1);
    expect(screen.getAllByText('Needs review before apply').length).toBeGreaterThan(1);
    expect(screen.getByText('No automatic changes were included because the system could not prove this branch was safe.')).toBeInTheDocument();
    expect(screen.getAllByText('security-autopilot-access-logs-123456789012').length).toBeGreaterThan(0);
    expect(screen.getByText('Shared setup diagnostics')).toBeInTheDocument();
    expect(screen.getByText('0 shared steps succeeded · 1 shared steps failed')).toBeInTheDocument();
    expect(screen.getByText('Shared S3.9 destination setup')).toBeInTheDocument();
    expect(screen.getByText('Shared destination setup failed.')).toBeInTheDocument();
    expect(screen.getByText(/Blocked by:/)).toBeInTheDocument();
    expect(screen.getByText('needs approval')).toBeInTheDocument();
    expect(screen.getByText(/Post-generation follow-up/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Hide outcomes' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Show outcomes' })).toBeInTheDocument();
    expect(screen.queryByText('Historical blocked action')).not.toBeInTheDocument();
  });

  it('expands older generation outcomes on demand', async () => {
    render(<ActionGroupDetailPage />);

    const showOutcomesButton = await screen.findByRole('button', { name: 'Show outcomes' });
    fireEvent.click(showOutcomesButton);

    expect(await screen.findByText('Historical blocked action')).toBeInTheDocument();
    expect(screen.getByText('Previous generation failed.')).toBeInTheDocument();
  });

  it('keeps manual-only grouped outcomes distinct from review-required ones', async () => {
    mockedGetActionGroupRuns.mockResolvedValue({
      items: [
        {
          id: 'run-manual',
          remediation_run_id: 'rem-run-manual',
          initiated_by_user_id: 'user-1',
          mode: 'download_bundle',
          status: 'finished',
          started_at: '2026-03-19T01:00:00Z',
          finished_at: '2026-03-19T01:05:00Z',
          reporting_source: 'bundle_callback',
          created_at: '2026-03-19T01:00:00Z',
          updated_at: '2026-03-19T01:05:00Z',
          shared_execution_results: [],
          results: [
            {
              action_id: 'action-2',
              execution_status: 'unknown',
              execution_error_code: null,
              execution_error_message: null,
              result_type: 'non_executable',
              support_tier: 'manual_guidance_only',
              reason: 'manual_guidance_metadata_only',
              blocked_reasons: ['approved defaults are missing'],
              decision_rationale: null,
              preservation_summary: {},
              strategy_inputs: {},
              execution_started_at: null,
              execution_finished_at: null,
            },
          ],
        },
      ],
      total: 1,
    } as never);

    render(<ActionGroupDetailPage />);

    await waitFor(() => {
      expect(mockedGetActionGroupRuns).toHaveBeenCalledWith('group-1', { limit: 100, offset: 0 }, undefined);
    });

    expect((await screen.findAllByText('Manual steps required')).length).toBeGreaterThan(0);
    expect(
      screen.getByText(
        'The platform cannot truthfully generate a safe automatic bundle from the current evidence or inputs.'
      )
    ).toBeInTheDocument();
  });

  it('resolves a remediation strategy before creating a grouped bundle run', async () => {
    render(<ActionGroupDetailPage />);

    await waitFor(() => {
      expect(mockedGetActionGroup).toHaveBeenCalledWith('group-1', undefined);
      expect(mockedGetActionGroupRuns).toHaveBeenCalledWith('group-1', { limit: 100, offset: 0 }, undefined);
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Generate bundle' }));

    await waitFor(() => {
      expect(mockedGetRemediationOptions).toHaveBeenCalledWith('action-1', undefined);
      expect(mockedCreateActionGroupBundleRun).toHaveBeenCalledWith(
        'group-1',
        {
          strategy_id: 'config_enable_account_local_delivery',
          strategy_inputs: {},
        },
        undefined
      );
    });
  });

  it('requires explicit risk acknowledgement before creating a warned grouped bundle run', async () => {
    const warnedS3Options = {
      action_id: 'action-1',
      action_type: 's3_block_public_access',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 's3_account_block_public_access_pr_bundle',
          label: 'Enable account-level S3 Block Public Access (PR bundle)',
          mode: 'pr_only',
          risk_level: 'low',
          recommended: true,
          requires_inputs: false,
          input_schema: { fields: [] },
          dependency_checks: [
            {
              code: 'risk_evaluation_not_specialized',
              status: 'unknown',
              message: 'No specialized dependency checks are available for this strategy yet.',
            },
          ],
          warnings: ['Review workloads that intentionally rely on public bucket policies before apply.'],
          supports_exception_flow: false,
          exception_only: false,
        },
      ],
      recommendation: {
        recommended_mode: 'pr_only',
        recommended_strategy_id: 's3_account_block_public_access_pr_bundle',
        rationale: [],
      },
      manual_high_risk: false,
      pre_execution_notice: null,
      runbook_url: null,
      manual_workflow: null,
    } as never;
    mockedGetRemediationOptions.mockResolvedValue(warnedS3Options);

    render(<ActionGroupDetailPage />);

    await waitFor(() => {
      expect(mockedGetActionGroup).toHaveBeenCalledWith('group-1', undefined);
    });

    const generateButton = await screen.findByRole('button', { name: 'Generate bundle' });
    fireEvent.click(generateButton);

    expect(await screen.findByText('Review required before generating this bundle.')).toBeInTheDocument();
    expect(screen.getByText('No specialized dependency checks are available for this strategy yet.')).toBeInTheDocument();
    expect(screen.getByText('Review workloads that intentionally rely on public bucket policies before apply.')).toBeInTheDocument();
    expect(mockedCreateActionGroupBundleRun).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('checkbox'));
    await waitFor(() => {
      expect(screen.getByRole('checkbox')).toBeChecked();
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Generate bundle' }));

    await waitFor(() => {
      expect(mockedCreateActionGroupBundleRun).toHaveBeenCalledWith(
        'group-1',
        {
          strategy_id: 's3_account_block_public_access_pr_bundle',
          strategy_inputs: {},
          risk_acknowledged: true,
        },
        undefined
      );
    });
    expect(mockedGetRemediationOptions).toHaveBeenCalledTimes(1);
  });

  it('surfaces backend risk acknowledgement requirements from grouped members and retries with acknowledgement', async () => {
    mockedCreateActionGroupBundleRun
      .mockRejectedValueOnce({
        error: 'Bad Request',
        status: 400,
        detail: {
          error: 'Risk acknowledgement required',
          detail: 'This remediation strategy has warning/unknown dependency checks. Set risk_acknowledged=true after review.',
          risk_snapshot: {
            checks: [
              {
                code: 's3_access_logging_scope_requires_review',
                status: 'warn',
                message: 'This S3.9 action is not bucket-scoped, so the exact source bucket cannot be derived automatically.',
              },
            ],
            warnings: ['Do not use the source bucket as the logging destination.'],
          },
        },
      } as never)
      .mockResolvedValueOnce({
        group_run_id: 'group-run-3',
        remediation_run_id: 'rem-run-3',
        reporting_token: 'token',
        reporting_callback_url: 'https://api.example.com/api/internal/group-runs/report',
        status: 'queued',
      } as never);

    render(<ActionGroupDetailPage />);

    await waitFor(() => {
      expect(mockedGetActionGroup).toHaveBeenCalledWith('group-1', undefined);
      expect(mockedGetActionGroupRuns).toHaveBeenCalledWith('group-1', { limit: 100, offset: 0 }, undefined);
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Generate bundle' }));

    await waitFor(() => {
      expect(mockedCreateActionGroupBundleRun).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByText('Review required before generating this bundle.')).toBeInTheDocument();
    const backendWarnedLabel = screen.getByText(
      'I reviewed the dependency warnings for this strategy and want to continue.'
    );
    fireEvent.click(backendWarnedLabel);
    await waitFor(() => {
      const checkbox = backendWarnedLabel.closest('label')?.querySelector('input[type="checkbox"]');
      expect(checkbox).toBeChecked();
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Generate bundle' })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate bundle' }));

    await waitFor(() => {
      expect(mockedCreateActionGroupBundleRun).toHaveBeenNthCalledWith(
        2,
        'group-1',
        {
          strategy_id: 'config_enable_account_local_delivery',
          strategy_inputs: {},
          risk_acknowledged: true,
        },
        undefined
      );
    });
    expect(mockedGetRemediationOptions).toHaveBeenCalledTimes(1);
  });

  it('shows compact source-first control family mapping for grouped action members', async () => {
    mockedGetActionGroup.mockResolvedValue({
      ...makeActionGroupDetail(),
      members: [
        {
          ...makeActionGroupDetail().members[0],
          control_id: 'EC2.53',
          control_family: {
            source_control_ids: ['EC2.19', 'EC2.18'],
            canonical_control_id: 'EC2.53',
            related_control_ids: ['EC2.53', 'EC2.13', 'EC2.18', 'EC2.19'],
            is_mapped: true,
          },
        },
      ],
      counters: {
        run_successful: 1,
        run_not_successful: 0,
        metadata_only: 0,
        not_run_yet: 0,
        total_actions: 1,
      },
    } as never);

    render(<ActionGroupDetailPage />);

    expect(await screen.findByText('EC2.19 +1 -> EC2.53 · resource-1')).toBeInTheDocument();
  });

});
