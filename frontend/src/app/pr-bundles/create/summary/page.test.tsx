import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

import PrBundleSummaryPage from './page';
import {
  createGroupPrBundleRun,
  createRemediationRun,
  getActions,
  getRemediationOptions,
} from '@/lib/api';

let searchParamValue = 'ids=action-1';
const push = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(searchParamValue),
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
}));

vi.mock('@/components/TenantIdForm', () => ({
  TenantIdForm: () => null,
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { id: 'user-1', role: 'admin' },
  }),
}));

vi.mock('@/lib/tenant', () => ({
  useTenantId: () => ({
    tenantId: null,
    setTenantId: vi.fn(),
  }),
}));

vi.mock('@/lib/api', () => ({
  createGroupPrBundleRun: vi.fn(),
  createRemediationRun: vi.fn(),
  getActions: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
  getRemediationOptions: vi.fn(),
}));

const mockedCreateGroupPrBundleRun = vi.mocked(createGroupPrBundleRun);
const mockedCreateRemediationRun = vi.mocked(createRemediationRun);
const mockedGetActions = vi.mocked(getActions);
const mockedGetRemediationOptions = vi.mocked(getRemediationOptions);

function makeAction(overrides: Record<string, unknown> = {}) {
  return {
    id: 'action-1',
    action_type: 'aws_config_enabled',
    target_id: 'target-1',
    account_id: '123456789012',
    region: 'us-east-1',
    score: 32,
    business_impact: {
      technical_risk_tier: 'medium',
      criticality: { tier: 'medium', status: 'known' },
    },
    priority: 32,
    status: 'open',
    title: 'Enable AWS Config',
    control_id: 'Config.1',
    resource_id: 'resource-1',
    updated_at: '2026-03-12T00:00:00Z',
    finding_count: 2,
    ...overrides,
  };
}

function makeRecommendation() {
  return {
    mode: 'pr_only',
    default_mode: 'pr_only',
    advisory: true,
    rationale: 'Use PR-only',
    matrix_position: {
      risk_tier: 'medium',
      business_criticality: 'medium',
      cell: 'medium:medium',
    },
    evidence: {
      score: 32,
      context_incomplete: false,
      data_sensitivity: 0,
      internet_exposure: 0,
      privilege_level: 0,
      exploit_signals: 0,
      matched_signals: [],
    },
  };
}

function makeOptions(overrides: Record<string, unknown> = {}) {
  return {
    action_id: 'action-1',
    action_type: 'aws_config_enabled',
    mode_options: ['pr_only'],
    strategies: [],
    recommendation: makeRecommendation(),
    manual_workflow: null,
    ...overrides,
  };
}

describe('PrBundleSummaryPage', () => {
  beforeEach(() => {
    mockedCreateGroupPrBundleRun.mockReset();
    mockedCreateRemediationRun.mockReset();
    mockedGetActions.mockReset();
    mockedGetRemediationOptions.mockReset();
    push.mockReset();
    searchParamValue = 'ids=action-1';
    mockedGetActions.mockResolvedValue({
      items: [makeAction()],
      total: 1,
    } as never);
    mockedCreateRemediationRun.mockResolvedValue({
      id: 'run-1',
      action_id: 'action-1',
      mode: 'pr_only',
      status: 'pending',
      created_at: '2026-03-12T00:00:00Z',
      updated_at: '2026-03-12T00:00:00Z',
    } as never);
    mockedCreateGroupPrBundleRun.mockResolvedValue({
      id: 'run-group-1',
      action_id: 'action-1',
      mode: 'pr_only',
      status: 'pending',
      created_at: '2026-03-12T00:00:00Z',
      updated_at: '2026-03-12T00:00:00Z',
    } as never);
    mockedGetRemediationOptions.mockResolvedValue(
      makeOptions({
        strategies: [
          {
            strategy_id: 'config_enable_account_local_delivery',
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
          },
        ],
      }) as never,
    );
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ip: '203.0.113.10' }),
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('preflights a single action and sends derived strategy payloads', async () => {
    const user = userEvent.setup();
    render(<PrBundleSummaryPage />);

    expect(await screen.findByRole('button', { name: 'Generate 1 PR bundle' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Run all plans/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Approve all apply/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Refresh execution status/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Generate 1 PR bundle' }));

    await waitFor(() => {
      expect(mockedGetRemediationOptions).toHaveBeenCalledWith('action-1', undefined);
      expect(mockedCreateRemediationRun).toHaveBeenCalledWith(
        'action-1',
        'pr_only',
        undefined,
        'config_enable_account_local_delivery',
        { delivery_bucket: 'security-autopilot-config-123456789012-us-east-1' },
      );
    });

    expect(await screen.findByText('Generation complete: 1 succeeded, 0 failed.')).toBeInTheDocument();
  });

  it('preflights grouped actions and sends one converged strategy payload', async () => {
    const user = userEvent.setup();
    searchParamValue = 'ids=action-1,action-2';
    mockedGetActions.mockResolvedValue({
      items: [
        makeAction(),
        makeAction({ id: 'action-2', target_id: 'target-2', resource_id: 'resource-2' }),
      ],
      total: 2,
    } as never);

    render(<PrBundleSummaryPage />);

    expect(await screen.findByText('Review the remediation bundle summary')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Generate 1 execution bundle' }));

    await waitFor(() => {
      expect(mockedGetRemediationOptions).toHaveBeenCalledTimes(2);
      expect(mockedCreateGroupPrBundleRun).toHaveBeenCalledWith(
        {
          action_type: 'aws_config_enabled',
          account_id: '123456789012',
          status: 'open',
          region: 'us-east-1',
          strategy_id: 'config_enable_account_local_delivery',
          strategy_inputs: { delivery_bucket: 'security-autopilot-config-123456789012-us-east-1' },
        },
        undefined,
      );
    });

    expect(await screen.findByText('Generation complete: 1 succeeded, 0 failed.')).toBeInTheDocument();
  });

  it('fails explicitly when required inputs are not safely derivable', async () => {
    const user = userEvent.setup();
    mockedGetRemediationOptions.mockResolvedValueOnce(
      makeOptions({
        action_id: 'action-1',
        action_type: 's3_bucket_access_logging',
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
                  description: 'Name of the log bucket.',
                },
              ],
            },
            dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
            warnings: [],
            supports_exception_flow: false,
            exception_only: false,
          },
        ],
      }) as never,
    );

    render(<PrBundleSummaryPage />);

    expect(await screen.findByRole('button', { name: 'Generate 1 PR bundle' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Generate 1 PR bundle' }));

    expect(await screen.findByText('Generation complete: 0 succeeded, 1 failed.')).toBeInTheDocument();
    expect(
      screen.getByText(/Required strategy inputs are not safely derivable: log_bucket_name\./),
    ).toBeInTheDocument();
    expect(mockedCreateRemediationRun).not.toHaveBeenCalled();
  });

  it('fails grouped generation explicitly when derived inputs differ across actions', async () => {
    const user = userEvent.setup();
    searchParamValue = 'ids=action-1,action-2';
    mockedGetActions.mockResolvedValue({
      items: [
        makeAction(),
        makeAction({ id: 'action-2', target_id: 'target-2', resource_id: 'resource-2' }),
      ],
      total: 2,
    } as never);
    mockedGetRemediationOptions
      .mockResolvedValueOnce(
        makeOptions({
          action_id: 'action-1',
          strategies: [
            {
              strategy_id: 'config_enable_account_local_delivery',
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
                  },
                ],
              },
              dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
              warnings: [],
              supports_exception_flow: false,
              exception_only: false,
              context: {
                default_inputs: {
                  delivery_bucket: 'security-autopilot-config-a',
                },
              },
            },
          ],
        }) as never,
      )
      .mockResolvedValueOnce(
        makeOptions({
          action_id: 'action-2',
          strategies: [
            {
              strategy_id: 'config_enable_account_local_delivery',
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
                  },
                ],
              },
              dependency_checks: [{ code: 'ok', status: 'pass', message: 'ok' }],
              warnings: [],
              supports_exception_flow: false,
              exception_only: false,
              context: {
                default_inputs: {
                  delivery_bucket: 'security-autopilot-config-b',
                },
              },
            },
          ],
        }) as never,
      );

    render(<PrBundleSummaryPage />);

    expect(await screen.findByText('Review the remediation bundle summary')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Generate 1 execution bundle' }));

    expect(await screen.findByText('Generation complete: 0 succeeded, 1 failed.')).toBeInTheDocument();
    expect(
      screen.getByText(/Auto-derived strategy inputs differ across grouped actions: action-1, action-2/),
    ).toBeInTheDocument();
    expect(mockedCreateGroupPrBundleRun).not.toHaveBeenCalled();
  });
});
