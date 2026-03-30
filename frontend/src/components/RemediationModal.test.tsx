import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ComponentProps, ReactNode } from 'react';
import { vi } from 'vitest';

import { RemediationModal } from '@/components/RemediationModal';
import {
  createRemediationRun,
  getRemediationOptions,
  getRemediationPreview,
  listManualWorkflowEvidence,
  listRemediationRuns,
  triggerActionReevaluation,
  type ActionRecommendation,
} from '@/lib/api';

const DEFAULT_RECOMMENDATION = {
  mode: 'pr_only',
  default_mode: 'pr_only',
  advisory: false,
  rationale: 'Recommended fix strategy.',
  matrix_position: {
    risk_tier: 'low',
    business_criticality: 'low',
    cell: 'A1',
  },
  evidence: {
    score: 0,
    context_incomplete: false,
    data_sensitivity: 0,
    internet_exposure: 0,
    privilege_level: 0,
    exploit_signals: 0,
    matched_signals: [],
  },
} satisfies ActionRecommendation;

vi.mock('@/components/ui/Modal', () => ({
  Modal: ({
    isOpen,
    title,
    headerContent,
    children,
  }: {
    isOpen: boolean;
    title: string;
    headerContent?: ReactNode;
    children: ReactNode;
  }) =>
    isOpen ? (
      <div>
        <div>
          <h2>{title}</h2>
          {headerContent}
        </div>
        {children}
      </div>
    ) : null,
}));

vi.mock('@/lib/api', () => ({
  createRemediationRun: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
  getRemediationOptions: vi.fn(),
  getRemediationPreview: vi.fn(),
  isApiError: () => false,
  listManualWorkflowEvidence: vi.fn(),
  listRemediationRuns: vi.fn(),
  triggerActionReevaluation: vi.fn(),
  uploadManualWorkflowEvidence: vi.fn(),
}));

const mockedCreateRemediationRun = vi.mocked(createRemediationRun);
const mockedGetRemediationOptions = vi.mocked(getRemediationOptions);
const mockedGetRemediationPreview = vi.mocked(getRemediationPreview);
const mockedListManualWorkflowEvidence = vi.mocked(listManualWorkflowEvidence);
const mockedListRemediationRuns = vi.mocked(listRemediationRuns);
const mockedTriggerActionReevaluation = vi.mocked(triggerActionReevaluation);

function renderModal(overrides: Partial<ComponentProps<typeof RemediationModal>> = {}) {
  const onChooseException = vi.fn();
  render(
    <RemediationModal
      isOpen={true}
      onClose={vi.fn()}
      actionId="action-1"
      actionTitle="Enable AWS Config"
      actionType="aws_config_enabled"
      accountId="123456789012"
      region="us-east-1"
      mode="pr_only"
      hasWriteRole={true}
      onChooseException={onChooseException}
      {...overrides}
    />,
  );
  return { onChooseException };
}

describe('RemediationModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ip: '203.0.113.10' }),
      }),
    );
    mockedGetRemediationOptions.mockResolvedValue({
      action_id: 'action-1',
      action_type: 'aws_config_enabled',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'config_keep_exception',
          label: 'Keep current state (exception path)',
          mode: 'pr_only',
          risk_level: 'high',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'exception_duration_days',
                type: 'select',
                required: false,
                description: 'How long should this exception remain active?',
                default_value: '30',
                options: [
                  { value: '7', label: '7 days' },
                  { value: '14', label: '14 days' },
                  { value: '30', label: '30 days' },
                  { value: '90', label: '90 days' },
                ],
              },
              {
                key: 'exception_reason',
                type: 'string',
                required: false,
                description: "Why can't you apply this fix right now?",
              },
            ],
          },
          dependency_checks: [
            {
              code: 'config_visibility_gap',
              status: 'warn',
              message: 'Keeping AWS Config disabled reduces visibility.',
            },
          ],
          warnings: ['Skipping Config reduces change visibility and audit evidence quality.'],
          supports_exception_flow: true,
          exception_only: true,
          rollback_command:
            'aws configservice stop-configuration-recorder --configuration-recorder-name <RECORDER_NAME>',
          estimated_resolution_time: '1-6 hours',
          supports_immediate_reeval: true,
        },
        {
          strategy_id: 'config_enable_account_local_delivery',
          label: 'Enable AWS Config with account-local delivery',
          mode: 'pr_only',
          risk_level: 'medium',
          recommended: false,
          requires_inputs: false,
          input_schema: { fields: [] },
          dependency_checks: [
            {
              code: 'config_cost_impact',
              status: 'warn',
              message: 'Enabling AWS Config may increase costs.',
            },
          ],
          warnings: ['Enabling Config can increase logging/storage costs.'],
          supports_exception_flow: false,
          exception_only: false,
          rollback_command:
            'aws configservice stop-configuration-recorder --configuration-recorder-name <RECORDER_NAME>',
          estimated_resolution_time: '1-6 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });
    mockedCreateRemediationRun.mockResolvedValue({
      id: 'run-1',
      action_id: 'action-1',
      mode: 'pr_only',
      status: 'pending',
      created_at: '2026-02-25T00:00:00Z',
      updated_at: '2026-02-25T00:00:00Z',
    });
    mockedGetRemediationPreview.mockResolvedValue({
      compliant: true,
      message: 'No changes required.',
      will_apply: false,
    });
    mockedListManualWorkflowEvidence.mockResolvedValue([]);
    mockedListRemediationRuns.mockResolvedValue({ items: [], total: 0 });
    mockedTriggerActionReevaluation.mockResolvedValue({
      message: 'Immediate re-evaluation jobs queued',
      tenant_id: 'tenant-1',
      action_id: 'action-1',
      strategy_id: 'config_keep_exception',
      estimated_resolution_time: '1-6 hours',
      supports_immediate_reeval: true,
      scope: { account_id: '123456789012', region: 'us-east-1' },
      enqueued_jobs: 2,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('routes explicit exception option with inline duration/reason and skips PR run creation', async () => {
    const user = userEvent.setup();
    const { onChooseException } = renderModal();

    await waitFor(() => {
      expect(mockedGetRemediationOptions).toHaveBeenCalledWith('action-1', undefined);
    });

    await user.click(screen.getByRole('radio', { name: /I need an exception/i }));
    expect(screen.getAllByRole('heading', { name: 'Create exception' }).length).toBeGreaterThan(0);
    expect(screen.getByText("I can't apply this fix right now — create a time-limited exception.")).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '7 days' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '14 days' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '30 days' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '90 days' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '14 days' }));
    await user.type(
      screen.getByLabelText(/Why can't you apply this fix right now/i),
      'Approved maintenance freeze window for this system.',
    );

    await user.click(screen.getByRole('button', { name: 'Create exception' }));

    expect(onChooseException).toHaveBeenCalledTimes(1);
    expect(onChooseException).toHaveBeenCalledWith(
      expect.objectContaining({
        strategy: expect.objectContaining({ strategy_id: 'config_keep_exception', exception_only: true }),
        strategyInputs: expect.objectContaining({
          exception_duration_days: '14',
          exception_reason: 'Approved maintenance freeze window for this system.',
        }),
      }),
    );
    expect(mockedCreateRemediationRun).not.toHaveBeenCalled();
  });

  it('shows Generate PR bundle when a non-exception strategy is selected', async () => {
    const user = userEvent.setup();
    renderModal();

    await waitFor(() => {
      expect(mockedGetRemediationOptions).toHaveBeenCalled();
    });

    await user.click(screen.getByRole('radio', { name: /Enable AWS Config with account-local delivery/i }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Generate PR Bundle' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Generate PR bundle' })).toBeInTheDocument();
    });
  });

  it('renders remediation strategy options as full-width cards', async () => {
    renderModal();

    await waitFor(() => {
      expect(mockedGetRemediationOptions).toHaveBeenCalled();
    });

    const strategyRadio = screen.getByRole('radio', {
      name: /Enable AWS Config with account-local delivery/i,
    });
    const strategyCard = strategyRadio.closest('label');

    expect(strategyCard).not.toBeNull();
    expect(strategyCard).toHaveClass('block');
    expect(strategyCard).toHaveClass('w-full');
  });

  it('shows explicit safety gate messaging when iam_root_key_delete is blocked by MFA gate', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-root',
      action_type: 'iam_root_access_key_absent',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'iam_root_key_delete',
          label: 'Delete root access key',
          mode: 'pr_only',
          risk_level: 'high',
          recommended: false,
          requires_inputs: false,
          input_schema: { fields: [] },
          dependency_checks: [
            {
              code: 'iam_root_mfa_enrollment_gate',
              status: 'fail',
              message:
                'Delete path is blocked: root MFA is not enrolled (AccountMFAEnabled=0). Enable root MFA before selecting root key delete.',
            },
          ],
          warnings: ['Gate: Root MFA must be active before this delete path is selectable.'],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '12-24 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    renderModal({
      actionId: 'action-root',
      actionType: 'iam_root_access_key_absent',
      actionTitle: 'Remove IAM root access key',
      accountId: '029037611564',
      region: 'eu-north-1',
    });

    await waitFor(() => {
      expect(screen.getByText('Safety gate blocked')).toBeInTheDocument();
    });
    expect(screen.getAllByText(/Delete path is blocked: root MFA is not enrolled/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Generate PR bundle' })).toBeDisabled();
  });

  it('renders grouped guided inputs with visibility, help text, impact preview, and typed payloads', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-1',
      action_type: 'sg_restrict_public_ports',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'sg_restrict_public_ports_guided',
          label: 'Secure remote admin access',
          mode: 'pr_only',
          risk_level: 'low',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'access_mode',
                type: 'select',
                required: true,
                description: 'How would you like to secure remote access?',
                default_value: 'close_public',
                group: 'Access Control',
                options: [
                  {
                    value: 'close_public',
                    label: 'Add restricted access without removing old public rules',
                    description: 'Closes public admin ports while keeping existing rules.',
                    impact_text: 'Public rules stay in place until manually removed.',
                  },
                  {
                    value: 'restrict_to_cidr',
                    label: 'Restrict to CIDR',
                    description: 'Limits admin access to the provided CIDR range.',
                    impact_text: 'Only the provided CIDR can access admin ports.',
                  },
                ],
              },
              {
                key: 'allowed_cidr',
                type: 'cidr',
                required: false,
                description: 'Allowed IPv4 CIDR',
                placeholder: '203.0.113.10/32',
                visible_when: { field: 'access_mode', equals: ['restrict_to_cidr'] },
                impact_text: 'SSH/RDP access is reduced to the approved CIDR.',
                group: 'Access Control',
              },
              {
                key: 'remove_existing_public_rules',
                type: 'boolean',
                required: false,
                description: 'Automatically remove existing public rules',
                default_value: true,
                help_text: 'Turn this on only if alternative access is already configured.',
                group: 'Advanced Settings',
              },
              {
                key: 'retry_limit',
                type: 'number',
                required: false,
                description: 'Maximum retry attempts',
                default_value: 2,
                min: 1,
                max: 5,
                impact_text: 'Higher retry limits can increase execution time.',
                group: 'Advanced Settings',
              },
            ],
          },
          dependency_checks: [
            {
              code: 'sg_access_ready',
              status: 'pass',
              message: 'Access checks passed.',
            },
          ],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '12-24 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    const user = userEvent.setup();
    renderModal();

    await waitFor(() => {
      expect(mockedGetRemediationOptions).toHaveBeenCalled();
    });

    expect(screen.getByText('Access Control')).toBeInTheDocument();
    expect(screen.getByText('Advanced Settings')).toBeInTheDocument();
    expect(
      screen.getByText('Closes public admin ports while keeping existing rules.')
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(/Help for Automatically remove existing public rules/i)
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/Allowed IPv4 CIDR/i)).not.toBeInTheDocument();

    await user.selectOptions(
      screen.getByLabelText(/How would you like to secure remote access/i),
      'restrict_to_cidr'
    );

    expect(screen.getByLabelText(/Allowed IPv4 CIDR/i)).toBeInTheDocument();
    expect(screen.getByText('Limits admin access to the provided CIDR range.')).toBeInTheDocument();
    expect(screen.getByText('Only the provided CIDR can access admin ports.')).toBeInTheDocument();
    expect(screen.getAllByText('Impact preview').length).toBeGreaterThan(0);

    await user.type(screen.getByLabelText(/Allowed IPv4 CIDR/i), '10.0.0.0');
    expect(screen.getByText(/Enter a valid CIDR/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generate PR bundle' })).toBeDisabled();

    const retryInput = screen.getByLabelText(/Maximum retry attempts/i);
    await user.clear(retryInput);
    await user.type(retryInput, '10');
    expect(screen.getByText('Value must be at most 5.')).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/Allowed IPv4 CIDR/i));
    await user.type(screen.getByLabelText(/Allowed IPv4 CIDR/i), '10.0.0.0/24');
    await user.clear(retryInput);
    await user.type(retryInput, '3');

    await waitFor(() => {
      expect(screen.queryByText('Value must be at most 5.')).not.toBeInTheDocument();
      expect(screen.queryByText(/Enter a valid CIDR/i)).not.toBeInTheDocument();
    });

    const autoRemoveSwitch = screen.getByRole('switch', {
      name: /Automatically remove existing public rules/i,
    });
    expect(autoRemoveSwitch).toHaveAttribute('aria-checked', 'true');
    await user.click(autoRemoveSwitch);
    expect(autoRemoveSwitch).toHaveAttribute('aria-checked', 'false');

    await user.click(screen.getByRole('button', { name: 'Generate PR bundle' }));

    await waitFor(() => {
      expect(mockedCreateRemediationRun).toHaveBeenCalledWith(
        'action-1',
        'pr_only',
        undefined,
        'sg_restrict_public_ports_guided',
        {
          access_mode: 'restrict_to_cidr',
          allowed_cidr: '10.0.0.0/24',
          remove_existing_public_rules: false,
          retry_limit: 3,
        },
        false,
        false,
      );
    });
  });

  it('detects public IP and prefills EC2.53 CIDR input', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-ec2-53',
      action_type: 'sg_restrict_public_ports',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'sg_restrict_public_ports_guided',
          label: 'Secure remote admin access',
          mode: 'pr_only',
          risk_level: 'low',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'access_mode',
                type: 'select',
                required: true,
                description: 'How would you like to secure remote access?',
                default_value: 'close_public',
                options: [
                  {
                    value: 'close_public',
                    label: 'Add restricted access without removing old public rules',
                  },
                  { value: 'restrict_to_ip', label: 'Restrict to my IP' },
                ],
              },
              {
                key: 'allowed_cidr',
                type: 'cidr',
                required: false,
                description: 'Allowed IPv4 CIDR',
                visible_when: { field: 'access_mode', equals: ['restrict_to_ip'] },
              },
            ],
          },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '12-24 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    const user = userEvent.setup();
    renderModal({
      actionId: 'action-ec2-53',
      actionType: 'sg_restrict_public_ports',
      actionTitle: 'Restrict public admin ports',
    });

    await waitFor(() => {
      expect(mockedGetRemediationOptions).toHaveBeenCalled();
    });

    await user.selectOptions(
      screen.getByLabelText(/How would you like to secure remote access/i),
      'restrict_to_ip',
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Allowed IPv4 CIDR/i)).toHaveValue('203.0.113.10/32');
    });
  });

  it('prefills Config strategy defaults from backend context', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-config',
      action_type: 'aws_config_enabled',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'config_enable_centralized_delivery',
          label: 'Enable AWS Config',
          mode: 'pr_only',
          risk_level: 'medium',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'recording_scope',
                type: 'select',
                required: false,
                description: 'How should AWS Config recording scope be set?',
                default_value: 'all_resources',
                options: [
                  { value: 'all_resources', label: 'All resources' },
                  { value: 'keep_existing', label: 'Keep existing scope' },
                ],
              },
              {
                key: 'delivery_bucket_mode',
                type: 'select',
                required: false,
                description: 'Where should AWS Config deliver snapshots and history?',
                default_value: 'create_new',
                options: [
                  { value: 'create_new', label: 'Create new dedicated bucket' },
                  { value: 'use_existing', label: 'Use existing bucket' },
                ],
              },
              {
                key: 'existing_bucket_name',
                type: 'string',
                required: false,
                description: 'Existing S3 bucket name for AWS Config delivery.',
                visible_when: { field: 'delivery_bucket_mode', equals: 'use_existing' },
              },
              {
                key: 'delivery_bucket',
                type: 'string',
                required: true,
                description: 'Centralized S3 bucket for Config delivery.',
              },
            ],
          },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '1-6 hours',
          supports_immediate_reeval: true,
          context: {
            default_inputs: {
              recording_scope: 'keep_existing',
              delivery_bucket_mode: 'use_existing',
              existing_bucket_name: 'security-autopilot-config-123456789012-us-east-1',
              delivery_bucket: 'security-autopilot-config-123456789012-us-east-1',
            },
          },
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    renderModal({
      actionId: 'action-config',
      actionType: 'aws_config_enabled',
      actionTitle: 'Enable AWS Config',
    });

    await waitFor(() => {
      expect(screen.getByLabelText(/How should AWS Config recording scope be set/i)).toHaveValue('keep_existing');
      expect(screen.getByLabelText(/Where should AWS Config deliver snapshots and history/i)).toHaveValue(
        'use_existing',
      );
      expect(screen.getByLabelText(/Existing S3 bucket name for AWS Config delivery/i)).toHaveValue(
        'security-autopilot-config-123456789012-us-east-1',
      );
      expect(screen.getByLabelText(/Centralized S3 bucket for Config delivery/i)).toHaveValue(
        'security-autopilot-config-123456789012-us-east-1',
      );
    });
  });

  it('prefills CloudTrail strategy defaults from backend context', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-cloudtrail',
      action_type: 'cloudtrail_enabled',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'cloudtrail_enable_guided',
          label: 'Enable CloudTrail logging',
          mode: 'pr_only',
          risk_level: 'medium',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'trail_name',
                type: 'string',
                required: false,
                description: 'Name for the CloudTrail trail.',
                default_value: 'security-autopilot-trail',
              },
              {
                key: 'create_bucket_policy',
                type: 'boolean',
                required: false,
                description: 'Automatically add required S3 bucket policy statements for CloudTrail delivery.',
                default_value: true,
              },
              {
                key: 'trail_bucket_name',
                type: 'string',
                required: false,
                description: 'CloudTrail log bucket.',
                safe_default_value: 'security-autopilot-trail-logs-{{account_id}}-{{region}}',
              },
              {
                key: 'create_bucket_if_missing',
                type: 'boolean',
                required: false,
                description: 'Create a new CloudTrail log bucket if the named bucket does not already exist.',
                default_value: true,
              },
              {
                key: 'multi_region',
                type: 'boolean',
                required: false,
                description: 'Enable CloudTrail logging across all regions.',
                default_value: true,
              },
            ],
          },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '1-6 hours',
          supports_immediate_reeval: true,
          context: {
            default_inputs: {
              trail_name: 'existing-org-trail',
              trail_bucket_name: 'existing-cloudtrail-logs',
              create_bucket_if_missing: false,
              create_bucket_policy: true,
              multi_region: false,
            },
          },
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    renderModal({
      actionId: 'action-cloudtrail',
      actionType: 'cloudtrail_enabled',
      actionTitle: 'Enable CloudTrail',
    });

    await waitFor(() => {
      expect(screen.getByLabelText(/Name for the CloudTrail trail/i)).toHaveValue('existing-org-trail');
      expect(screen.getByDisplayValue('existing-cloudtrail-logs')).toBeInTheDocument();
    });

    const multiRegionSwitch = screen.getByRole('switch', {
      name: /Enable CloudTrail logging across all regions/i,
    });
    expect(multiRegionSwitch).toHaveAttribute('aria-checked', 'false');
  });

  it('prefills CloudTrail tenant-default bucket from resolver-backed option defaults', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-cloudtrail-tenant-default',
      action_type: 'cloudtrail_enabled',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'cloudtrail_enable_guided',
          label: 'Enable CloudTrail logging',
          mode: 'pr_only',
          risk_level: 'medium',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'trail_name',
                type: 'string',
                required: false,
                description: 'Name for the CloudTrail trail.',
                default_value: 'security-autopilot-trail',
              },
              {
                key: 'trail_bucket_name',
                type: 'string',
                required: false,
                description: 'CloudTrail log bucket.',
                safe_default_value: 'security-autopilot-trail-logs-{{account_id}}-{{region}}',
              },
              {
                key: 'create_bucket_if_missing',
                type: 'boolean',
                required: false,
                description: 'Create a new CloudTrail log bucket if the named bucket does not already exist.',
                default_value: true,
              },
              {
                key: 'create_bucket_policy',
                type: 'boolean',
                required: false,
                description: 'Automatically add required S3 bucket policy statements for CloudTrail delivery.',
                default_value: true,
              },
              {
                key: 'multi_region',
                type: 'boolean',
                required: false,
                description: 'Enable CloudTrail logging across all regions.',
                default_value: true,
              },
            ],
          },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '1-6 hours',
          supports_immediate_reeval: true,
          context: {
            default_inputs: {
              trail_name: 'security-autopilot-trail',
              trail_bucket_name: 'tenant-cloudtrail-logs',
              create_bucket_if_missing: false,
              create_bucket_policy: true,
              multi_region: true,
            },
          },
          preservation_summary: {
            trail_bucket_mode: 'existing',
            trail_bucket_source: 'tenant_default',
          },
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    renderModal({
      actionId: 'action-cloudtrail-tenant-default',
      actionType: 'cloudtrail_enabled',
      actionTitle: 'Enable CloudTrail',
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue('tenant-cloudtrail-logs')).toBeInTheDocument();
    });

    expect(
      screen.getByRole('switch', {
        name: /Create a new CloudTrail log bucket if the named bucket does not already exist/i,
      }),
    ).toHaveAttribute('aria-checked', 'false');
  });

  it('requires explicit approval when CloudTrail safe-default bucket creation is enabled by default', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-cloudtrail',
      action_type: 'cloudtrail_enabled',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'cloudtrail_enable_guided',
          label: 'Enable CloudTrail logging',
          mode: 'pr_only',
          risk_level: 'medium',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'trail_name',
                type: 'string',
                required: false,
                description: 'Name for the CloudTrail trail.',
                default_value: 'security-autopilot-trail',
              },
              {
                key: 'trail_bucket_name',
                type: 'string',
                required: false,
                description: 'CloudTrail log bucket.',
                safe_default_value: 'security-autopilot-trail-logs-{{account_id}}-{{region}}',
              },
              {
                key: 'create_bucket_if_missing',
                type: 'boolean',
                required: false,
                description: 'Create a new CloudTrail log bucket if the named bucket does not already exist.',
                default_value: true,
              },
              {
                key: 'create_bucket_policy',
                type: 'boolean',
                required: false,
                description: 'Automatically add required S3 bucket policy statements for CloudTrail delivery.',
                default_value: true,
              },
              {
                key: 'multi_region',
                type: 'boolean',
                required: false,
                description: 'Enable CloudTrail logging across all regions.',
                default_value: true,
              },
            ],
          },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '1-6 hours',
          supports_immediate_reeval: false,
          preservation_summary: {
            trail_bucket_mode: 'create_if_missing',
          },
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    const user = userEvent.setup();
    renderModal({
      actionId: 'action-cloudtrail',
      actionType: 'cloudtrail_enabled',
      actionTitle: 'Enable CloudTrail',
    });

    await waitFor(() => {
      expect(
        screen.getByDisplayValue('security-autopilot-trail-logs-123456789012-us-east-1'),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole('switch', {
        name: /Create a new CloudTrail log bucket if the named bucket does not already exist/i,
      }),
    ).toHaveAttribute('aria-checked', 'true');

    const submitButton = screen.getByRole('button', { name: 'Generate PR bundle' });
    expect(submitButton).toBeDisabled();

    await user.click(
      screen.getByRole('checkbox', {
        name: /I approve creating a new S3 bucket and bucket policy for CloudTrail log delivery/i,
      }),
    );

    await waitFor(() => expect(submitButton).not.toBeDisabled());
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockedCreateRemediationRun).toHaveBeenCalledWith(
        'action-cloudtrail',
        'pr_only',
        undefined,
        'cloudtrail_enable_guided',
        {
          trail_name: 'security-autopilot-trail',
          trail_bucket_name: 'security-autopilot-trail-logs-123456789012-us-east-1',
          create_bucket_if_missing: true,
          create_bucket_policy: true,
          multi_region: true,
        },
        false,
        true,
      );
    });
  });

  it('surfaces canonical resolver decisions for review-required preview paths', async () => {
    mockedGetRemediationPreview.mockResolvedValue({
      compliant: false,
      message: 'Preview for mode pr_only is informational only.',
      will_apply: false,
      diff_lines: [],
      resolution: {
        strategy_id: 'config_enable_account_local_delivery',
        profile_id: 'config_enable_account_local_delivery',
        support_tier: 'review_required_bundle',
        blocked_reasons: ['existing delivery bucket policy must be preserved'],
        missing_defaults: ['config_delivery_bucket_name'],
        preservation_summary: {
          apply_time_merge: true,
          merge_reason: 'customer-side delivery policy must be read at apply time',
        },
        decision_rationale:
          'The strategy stays additive, but the customer must review the generated bundle before apply.',
        decision_version: 'v1',
      },
    });

    renderModal();

    expect(await screen.findByRole('heading', { name: 'Execution decision' })).toBeInTheDocument();
    expect(screen.getByText('Needs review before apply')).toBeInTheDocument();
    expect(screen.getByText('Why the system chose this path')).toBeInTheDocument();
    expect(screen.getByText('What must be preserved')).toBeInTheDocument();
    expect(screen.getByText('What you should check next')).toBeInTheDocument();
    expect(screen.getByText('Review checklist')).toBeInTheDocument();
    expect(
      screen.getByText(
        'The strategy stays additive, but the customer must review the generated bundle before apply.'
      )
    ).toBeInTheDocument();
    expect(screen.getByText('review_required_bundle')).toBeInTheDocument();
    expect(screen.getByText('Policy and merge behavior')).toBeInTheDocument();
    expect(screen.getAllByText(/Provide or confirm config_delivery_bucket_name before apply/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Confirm this review condition: existing delivery bucket policy must be preserved/i).length).toBeGreaterThan(0);
    expect(
      screen.getAllByRole('link', { name: 'Configure AWS Config bucket defaults' })[0]
    ).toHaveAttribute('href', '/settings?tab=remediation-defaults#config-default-bucket-name');
    expect(screen.getAllByText('Verify preserved apply time merge').length).toBeGreaterThan(0);
    expect(screen.getByText('Verify preserved merge reason')).toBeInTheDocument();
    expect(screen.getByText('apply time merge')).toBeInTheDocument();
    expect(screen.getAllByText('Yes').length).toBeGreaterThan(0);
    expect(
      screen.getAllByText('customer-side delivery policy must be read at apply time').length,
    ).toBeGreaterThan(0);
  });

  it('keeps manual-only preview wording distinct from review-required copy', async () => {
    mockedGetRemediationPreview.mockResolvedValue({
      compliant: false,
      message: 'Preview for mode pr_only is informational only.',
      will_apply: false,
      diff_lines: [],
      resolution: {
        strategy_id: 'config_enable_account_local_delivery',
        profile_id: 'config_enable_account_local_delivery',
        support_tier: 'manual_guidance_only',
        blocked_reasons: ['approved tenant defaults are missing'],
        missing_defaults: ['cloudtrail_default_bucket_name'],
        preservation_summary: {},
        decision_rationale:
          'The platform cannot safely generate a runnable bundle until the required operator inputs are available.',
        decision_version: 'v1',
      },
    });

    renderModal();

    expect(await screen.findByText('Manual steps required')).toBeInTheDocument();
    expect(screen.getByText('What you should check next')).toBeInTheDocument();
    expect(
      screen.getByText(
        'The platform cannot truthfully generate a safe automatic bundle from the current evidence or inputs.'
      )
    ).toBeInTheDocument();
    expect(screen.getByText(/Provide or confirm cloudtrail_default_bucket_name before apply/i)).toBeInTheDocument();
    expect(screen.getByText('manual_guidance_only')).toBeInTheDocument();
    expect(screen.queryByText('Review checklist')).not.toBeInTheDocument();
    expect(
      screen.queryByText('The platform generated a truthful bundle, but an operator still needs to review the change before apply.')
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Configure CloudTrail bucket defaults' })
    ).toHaveAttribute('href', '/settings?tab=remediation-defaults#cloudtrail-default-bucket-name');
  });

  it('keeps blocked-reason prompts as plain text when no missing default maps to settings', async () => {
    mockedGetRemediationPreview.mockResolvedValue({
      compliant: false,
      message: 'Preview for mode pr_only is informational only.',
      will_apply: false,
      diff_lines: [],
      resolution: {
        strategy_id: 'config_enable_account_local_delivery',
        profile_id: 'config_enable_account_local_delivery',
        support_tier: 'review_required_bundle',
        blocked_reasons: ['existing delivery bucket policy must be preserved'],
        missing_defaults: [],
        preservation_summary: {},
        decision_rationale:
          'Review is required because the product cannot validate the existing customer policy shape from current evidence.',
        decision_version: 'v1',
      },
    });

    renderModal();

    expect(
      await screen.findByText('Review is required because the product cannot validate the existing customer policy shape from current evidence.')
    ).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Configure .* defaults/i })).not.toBeInTheDocument();
  });

  it('applies safe default for S3.15 key mode escape hatch', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-s3-kms',
      action_type: 's3_bucket_encryption_kms',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 's3_enable_sse_kms_guided',
          label: 'Enable S3 default encryption (SSE-KMS)',
          mode: 'pr_only',
          risk_level: 'low',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'kms_key_mode',
                type: 'select',
                required: false,
                description: 'Select which KMS key mode to use for default bucket encryption.',
                default_value: 'custom',
                options: [
                  { value: 'aws_managed', label: 'AWS managed key (aws/s3)' },
                  { value: 'custom', label: 'Custom KMS key' },
                ],
                safe_default_value: 'aws_managed',
              },
            ],
          },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '12-24 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    const user = userEvent.setup();
    renderModal({
      actionId: 'action-s3-kms',
      actionType: 's3_bucket_encryption_kms',
      actionTitle: 'Enable S3 KMS encryption',
    });

    const modeSelect = await screen.findByLabelText(/Select which KMS key mode/i);
    expect(modeSelect).toHaveValue('custom');

    await user.click(screen.getByRole('button', { name: /Not sure\? Use safe default/i }));
    expect(modeSelect).toHaveValue('aws_managed');
  });

  it('applies safe default for EC2.53 CIDR escape hatch', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-ec2-safe-default',
      action_type: 'sg_restrict_public_ports',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'sg_restrict_public_ports_guided',
          label: 'Secure remote admin access',
          mode: 'pr_only',
          risk_level: 'low',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'access_mode',
                type: 'select',
                required: true,
                description: 'How would you like to secure remote access?',
                default_value: 'restrict_to_ip',
                options: [
                  {
                    value: 'close_public',
                    label: 'Add restricted access without removing old public rules',
                  },
                  { value: 'restrict_to_ip', label: 'Restrict to my IP' },
                ],
              },
              {
                key: 'allowed_cidr',
                type: 'cidr',
                required: false,
                description: 'Allowed IPv4 CIDR',
                visible_when: { field: 'access_mode', equals: ['restrict_to_ip'] },
                safe_default_value: '{{detected_public_ipv4_cidr}}',
              },
            ],
          },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '12-24 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    const user = userEvent.setup();
    renderModal({
      actionId: 'action-ec2-safe-default',
      actionType: 'sg_restrict_public_ports',
      actionTitle: 'Restrict public SSH/RDP',
    });

    const cidrInput = await screen.findByLabelText(/Allowed IPv4 CIDR/i);
    await user.clear(cidrInput);
    await user.type(cidrInput, '10.0.0.0/24');
    expect(cidrInput).toHaveValue('10.0.0.0/24');

    await user.click(screen.getByRole('button', { name: /Not sure\? Use safe default/i }));
    expect(cidrInput).toHaveValue('203.0.113.10/32');
  });

  it('does not reset EC2.53 access mode when no CIDR safe default is available', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-ec2-no-safe-default',
      action_type: 'sg_restrict_public_ports',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'sg_restrict_public_ports_guided',
          label: 'Secure remote admin access',
          mode: 'pr_only',
          risk_level: 'low',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'access_mode',
                type: 'select',
                required: true,
                description: 'How would you like to secure remote access?',
                default_value: 'restrict_to_ip',
                options: [
                  {
                    value: 'close_public',
                    label: 'Add restricted access without removing old public rules',
                  },
                  { value: 'restrict_to_ip', label: 'Restrict to my IP' },
                ],
              },
              {
                key: 'allowed_cidr',
                type: 'cidr',
                required: false,
                description: 'Allowed IPv4 CIDR',
                visible_when: { field: 'access_mode', equals: ['restrict_to_ip'] },
                safe_default_value: '{{unsupported_token}}',
              },
            ],
          },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '12-24 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    const user = userEvent.setup();
    renderModal({
      actionId: 'action-ec2-no-safe-default',
      actionType: 'sg_restrict_public_ports',
      actionTitle: 'Restrict public SSH/RDP',
    });

    const cidrInput = await screen.findByLabelText(/Allowed IPv4 CIDR/i);
    expect(screen.getByLabelText(/How would you like to secure remote access/i)).toHaveValue('restrict_to_ip');

    await user.clear(cidrInput);
    await user.type(cidrInput, '10.0.0.0/24');
    await user.click(screen.getByRole('button', { name: /Not sure\? Use safe default/i }));

    expect(screen.getByLabelText(/How would you like to secure remote access/i)).toHaveValue('restrict_to_ip');
    expect(screen.getByLabelText(/Allowed IPv4 CIDR/i)).toHaveValue('10.0.0.0/24');
  });

  it('applies safe default for Config delivery bucket escape hatch', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-config-safe-default',
      action_type: 'aws_config_enabled',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'config_enable_centralized_delivery',
          label: 'Enable AWS Config',
          mode: 'pr_only',
          risk_level: 'medium',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'delivery_bucket',
                type: 'string',
                required: true,
                description: 'Centralized S3 bucket for Config delivery.',
                safe_default_value: 'security-autopilot-config-{{account_id}}-{{region}}',
              },
            ],
          },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '1-6 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    const user = userEvent.setup();
    renderModal({
      actionId: 'action-config-safe-default',
      actionType: 'aws_config_enabled',
      actionTitle: 'Enable AWS Config',
      accountId: '123456789012',
    });

    const bucketInput = await screen.findByLabelText(/Centralized S3 bucket for Config delivery/i);
    expect(bucketInput).toHaveValue('');

    await user.click(screen.getByRole('button', { name: /Not sure\? Use safe default/i }));
    expect(bucketInput).toHaveValue('security-autopilot-config-123456789012-us-east-1');
  });

  it('applies safe default for S3.9 log bucket escape hatch', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-s3-logging-safe-default',
      action_type: 's3_bucket_access_logging',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 's3_enable_access_logging_guided',
          label: 'Enable S3 access logging',
          mode: 'pr_only',
          risk_level: 'low',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'log_bucket_name',
                type: 'string',
                required: true,
                description: 'Name of the S3 bucket that receives access logs.',
                safe_default_value: 'security-autopilot-access-logs-{{account_id}}',
              },
            ],
          },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '12-24 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    const user = userEvent.setup();
    renderModal({
      actionId: 'action-s3-logging-safe-default',
      actionType: 's3_bucket_access_logging',
      actionTitle: 'Enable S3 access logging',
      accountId: '123456789012',
    });

    const bucketInput = await screen.findByLabelText(/Name of the S3 bucket that receives access logs/i);
    expect(bucketInput).toHaveValue('');

    await user.click(screen.getByRole('button', { name: /Not sure\? Use safe default/i }));
    expect(bucketInput).toHaveValue('security-autopilot-access-logs-123456789012');
  });

  it('applies safe default for CloudTrail trail name escape hatch', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-cloudtrail-safe-default',
      action_type: 'cloudtrail_enabled',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'cloudtrail_enable_guided',
          label: 'Enable CloudTrail',
          mode: 'pr_only',
          risk_level: 'medium',
          recommended: true,
          requires_inputs: true,
          input_schema: {
            fields: [
              {
                key: 'trail_name',
                type: 'string',
                required: false,
                description: 'Name for the CloudTrail trail.',
                safe_default_value: 'security-autopilot-trail',
              },
            ],
          },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '1-6 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    const user = userEvent.setup();
    renderModal({
      actionId: 'action-cloudtrail-safe-default',
      actionType: 'cloudtrail_enabled',
      actionTitle: 'Enable CloudTrail',
    });

    const trailNameInput = await screen.findByLabelText(/Name for the CloudTrail trail/i);
    await user.type(trailNameInput, 'temporary-name');
    expect(trailNameInput).toHaveValue('temporary-name');

    await user.click(screen.getByRole('button', { name: /Not sure\? Use safe default/i }));
    expect(trailNameInput).toHaveValue('security-autopilot-trail');
  });

  it('renders collapsed rollback recipe and supports copy', async () => {
    const clipboardWriteSpy = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined);
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-rollback',
      action_type: 's3_bucket_require_ssl',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 's3_enforce_ssl_strict_deny',
          label: 'Enforce SSL-only S3 requests',
          mode: 'pr_only',
          risk_level: 'high',
          recommended: true,
          requires_inputs: false,
          input_schema: { fields: [] },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          rollback_command: 'aws s3api delete-bucket-policy --bucket <BUCKET_NAME>',
          estimated_resolution_time: '12-24 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    const user = userEvent.setup();
    renderModal({
      actionId: 'action-rollback',
      actionType: 's3_bucket_require_ssl',
      actionTitle: 'Enforce SSL for S3 bucket',
    });

    await waitFor(() => {
      expect(mockedGetRemediationOptions).toHaveBeenCalled();
    });

    await user.click(screen.getByText('How to undo this'));
    expect(
      screen.getByText('aws s3api delete-bucket-policy --bucket <BUCKET_NAME>'),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Copy command' }));
    await waitFor(() => {
      expect(clipboardWriteSpy).toHaveBeenCalledWith(
        'aws s3api delete-bucket-policy --bucket <BUCKET_NAME>',
      );
    });
    expect(screen.getByRole('button', { name: 'Copied' })).toBeInTheDocument();
    clipboardWriteSpy.mockRestore();
  });

  it('renders blast radius header badge with tooltip text for selected strategy', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-blast',
      action_type: 'sg_restrict_public_ports',
      mode_options: ['pr_only'],
      strategies: [
        {
          strategy_id: 'sg_restrict_public_ports_guided',
          label: 'Restrict public admin ports',
          mode: 'pr_only',
          risk_level: 'high',
          recommended: true,
          requires_inputs: false,
          input_schema: { fields: [] },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          blast_radius: 'access_changing',
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    renderModal({
      actionId: 'action-blast',
      actionType: 'sg_restrict_public_ports',
      actionTitle: 'Restrict public SSH/RDP',
    });

    const badge = await screen.findByTestId('blast-radius-badge');
    expect(badge).toHaveTextContent('Access-changing · Review first');
    expect(badge).toHaveClass('text-danger');
    expect(badge).toHaveAttribute(
      'title',
      'Can change access paths or remove existing permissions. Verify operational access before apply.',
    );
  });

  it('submits direct-fix with re-evaluation checkbox and triggers immediate re-eval', async () => {
    mockedGetRemediationOptions.mockResolvedValueOnce({
      action_id: 'action-direct',
      action_type: 's3_block_public_access',
      mode_options: ['direct_fix', 'pr_only'],
      strategies: [
        {
          strategy_id: 's3_account_block_public_access_direct_fix',
          label: 'Enable account-level S3 Block Public Access (direct fix)',
          mode: 'direct_fix',
          risk_level: 'low',
          recommended: true,
          requires_inputs: false,
          input_schema: { fields: [] },
          dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
          warnings: [],
          supports_exception_flow: false,
          exception_only: false,
          estimated_resolution_time: '12-24 hours',
          supports_immediate_reeval: true,
        },
      ],
      recommendation: DEFAULT_RECOMMENDATION,
      manual_workflow: null,
    });

    mockedCreateRemediationRun.mockResolvedValueOnce({
      id: 'run-direct-1',
      action_id: 'action-direct',
      mode: 'direct_fix',
      status: 'pending',
      created_at: '2026-03-04T00:00:00Z',
      updated_at: '2026-03-04T00:00:00Z',
    });
    mockedGetRemediationPreview.mockResolvedValueOnce({
      compliant: false,
      message: 'Direct fix can be applied.',
      will_apply: true,
    });
    mockedTriggerActionReevaluation.mockResolvedValueOnce({
      message: 'Immediate re-evaluation jobs queued',
      tenant_id: 'tenant-1',
      action_id: 'action-direct',
      strategy_id: 's3_account_block_public_access_direct_fix',
      estimated_resolution_time: '12-24 hours',
      supports_immediate_reeval: true,
      scope: { account_id: '123456789012' },
      enqueued_jobs: 2,
    });

    const user = userEvent.setup();
    renderModal({
      actionId: 'action-direct',
      actionTitle: 'Enable account-level S3 block public access',
      actionType: 's3_block_public_access',
      mode: 'direct_fix',
    });

    await waitFor(() => {
      expect(screen.getByText(/Estimated time to Security Hub PASSED/i)).toBeInTheDocument();
      expect(screen.getByText('12-24 hours')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('checkbox', { name: /Trigger re-evaluation after apply/i }));
    await user.click(screen.getByRole('button', { name: 'Approve & run' }));

    await waitFor(() => {
      expect(mockedCreateRemediationRun).toHaveBeenCalledWith(
        'action-direct',
        'direct_fix',
        undefined,
        's3_account_block_public_access_direct_fix',
        {},
        false,
        false,
      );
    });
    await waitFor(() => {
      expect(mockedTriggerActionReevaluation).toHaveBeenCalledWith(
        'action-direct',
        undefined,
        's3_account_block_public_access_direct_fix',
      );
    });
  });
});
