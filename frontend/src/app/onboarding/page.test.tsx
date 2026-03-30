import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import OnboardingPage from '@/app/onboarding/page';
import { useAuth } from '@/contexts/AuthContext';
import { useBackgroundJobs } from '@/contexts/BackgroundJobsContext';
import {
  checkAccountControlPlaneReadiness,
  getAccounts,
  sendSyntheticControlPlaneEvent,
  sendSyntheticControlPlaneEventForAccount,
} from '@/lib/api';

const mockReplace = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    replace: mockReplace,
  }),
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('@/contexts/BackgroundJobsContext', () => ({
  useBackgroundJobs: vi.fn(),
}));

vi.mock('@/components/ui', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}));

vi.mock('@/components/ui/SelectDropdown', () => ({
  SelectDropdown: ({ options, value, 'aria-label': ariaLabel }: { options?: Array<{ value: string; label: string }>; value?: string; 'aria-label'?: string }) => (
    <select aria-label={ariaLabel ?? 'Select'} defaultValue={value ?? ''}>
      {(options ?? []).map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
}));

vi.mock('@/lib/api', () => ({
  getAccounts: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
  registerAccount: vi.fn(),
  updateAccount: vi.fn(),
  checkAccountControlPlaneReadiness: vi.fn(),
  checkAccountServiceReadiness: vi.fn(),
  sendSyntheticControlPlaneEvent: vi.fn(),
  sendSyntheticControlPlaneEventForAccount: vi.fn(),
  triggerOnboardingFastPath: vi.fn(),
  triggerComputeActions: vi.fn(),
  triggerIngest: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseBackgroundJobs = vi.mocked(useBackgroundJobs);
const mockedGetAccounts = vi.mocked(getAccounts);
const mockedCheckAccountControlPlaneReadiness = vi.mocked(checkAccountControlPlaneReadiness);
const mockedSendSyntheticControlPlaneEvent = vi.mocked(sendSyntheticControlPlaneEvent);
const mockedSendSyntheticControlPlaneEventForAccount = vi.mocked(sendSyntheticControlPlaneEventForAccount);

function buildDraft(overrides: Record<string, unknown> = {}) {
  return {
    version: 2,
    updatedAt: Date.now(),
    step: 'control-plane',
    accountId: '123456789012',
    integrationRoleArn: 'arn:aws:iam::123456789012:role/SecurityAutopilotReadRole',
    regions: ['us-east-1'],
    controlPlaneRegion: 'us-east-1',
    controlPlaneStackName: '',
    connectedAccountId: 'account-1',
    inspectorVerified: true,
    securityHubConfigVerified: true,
    controlPlaneVerified: false,
    fastPathTriggered: false,
    fastPathComputeQueued: false,
    fastPathLastAttemptAt: null,
    firstIngestQueuedAt: null,
    firstIngestQueueMode: null,
    integrationValidatedAt: Date.now(),
    lastServiceCheckAt: Date.now(),
    lastControlPlaneCheckAt: null,
    ...overrides,
  };
}

function buildAccount() {
  return {
    id: 'account-1',
    account_id: '123456789012',
    role_read_arn: 'arn:aws:iam::123456789012:role/SecurityAutopilotReadRole',
    role_write_arn: null,
    regions: ['us-east-1'],
    status: 'validated' as const,
    last_validated_at: '2026-03-11T12:00:00Z',
    created_at: '2026-03-11T12:00:00Z',
    updated_at: '2026-03-11T12:00:00Z',
  };
}

function buildAuthState(isLoading: boolean) {
  return {
    user: {
      id: 'user-1',
      email: 'admin@example.com',
      name: 'Admin User',
      role: 'admin' as const,
      onboarding_completed_at: null,
      is_saas_admin: false,
      phone_number: null,
      phone_verified: false,
      email_verified: true,
    },
    tenant: {
      id: 'tenant-1',
      name: 'Tenant One',
      external_id: 'external-123',
    },
    isLoading,
    isAuthenticated: true,
    saas_account_id: '029037611564',
    read_role_launch_stack_url: null,
    read_role_template_url: null,
    read_role_region: 'eu-north-1',
    read_role_default_stack_name: 'SecurityAutopilotReadRole',
    write_role_launch_stack_url: null,
    write_role_template_url: null,
    write_role_default_stack_name: 'SecurityAutopilotWriteRole',
    control_plane_token: null,
    control_plane_token_fingerprint: null,
    control_plane_token_created_at: null,
    control_plane_token_revoked_at: null,
    control_plane_token_active: false,
    control_plane_forwarder_launch_stack_url: null,
    control_plane_forwarder_template_url: 'https://example.com/control-plane.yaml',
    control_plane_ingest_url: 'https://api.example.com/control-plane/ingest',
    control_plane_forwarder_default_stack_name: 'SecurityAutopilotControlPlaneForwarder',
    login: vi.fn(),
    completeMfaLogin: vi.fn(),
    signup: vi.fn(),
    acceptInvite: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    markOnboardingComplete: vi.fn(),
    rotateControlPlaneToken: vi.fn(),
    revokeControlPlaneToken: vi.fn(),
    buildReadRoleLaunchStackUrl: vi.fn(() => 'https://example.com/read-role'),
    buildWriteRoleLaunchStackUrl: vi.fn(() => 'https://example.com/write-role'),
    buildControlPlaneForwarderLaunchStackUrl: vi.fn(() => 'https://example.com/control-plane'),
    mutateUser: vi.fn(),
  } as ReturnType<typeof useAuth>;
}

describe('OnboardingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('open', vi.fn());
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: vi.fn(() => null),
        setItem: vi.fn(),
        removeItem: vi.fn(),
      },
      configurable: true,
    });
    mockedGetAccounts.mockResolvedValue([]);
    mockedCheckAccountControlPlaneReadiness.mockResolvedValue({
      account_id: '123456789012',
      stale_after_minutes: 30,
      overall_ready: true,
      missing_regions: [],
      regions: [],
    });
    mockedSendSyntheticControlPlaneEvent.mockResolvedValue({
      enqueued: 1,
      dropped: 0,
      drop_reasons: {},
    });
    mockedSendSyntheticControlPlaneEventForAccount.mockResolvedValue({
      enqueued: 1,
      dropped: 0,
      drop_reasons: {},
    });
    mockedUseBackgroundJobs.mockReturnValue({
      jobs: [],
      activeCount: 0,
      addJob: vi.fn(() => 'job-1'),
      updateJob: vi.fn(),
      completeJob: vi.fn(),
      failJob: vi.fn(),
      timeoutJob: vi.fn(),
      cancelJob: vi.fn(),
      dismissBanner: vi.fn(),
      dismissJob: vi.fn(),
      clearFinishedJobs: vi.fn(),
    });
  });

  it('renders after auth loading resolves without crashing on rerender', async () => {
    const authState = buildAuthState(true);
    mockedUseAuth.mockImplementation(() => authState);

    const { rerender } = render(<OnboardingPage />);

    expect(screen.getByText('Loading onboarding...')).toBeInTheDocument();

    Object.assign(authState, buildAuthState(false));
    rerender(<OnboardingPage />);

    expect(await screen.findByRole('button', { name: 'Start onboarding' })).toBeInTheDocument();
    expect(mockedGetAccounts).toHaveBeenCalledTimes(1);
  });

  it('shows fake verify-intake progress while readiness polling is still pending', async () => {
    let resolveReadiness: ((value: {
      account_id: string;
      stale_after_minutes: number;
      overall_ready: boolean;
      missing_regions: string[];
      regions: never[];
    }) => void) | null = null;
    const pendingReadiness = new Promise<{
      account_id: string;
      stale_after_minutes: number;
      overall_ready: boolean;
      missing_regions: string[];
      regions: never[];
    }>((resolve) => {
      resolveReadiness = resolve;
    });
    mockedUseAuth.mockReturnValue({
      ...buildAuthState(false),
      control_plane_token: 'token-123',
      control_plane_token_active: true,
    });
    mockedGetAccounts.mockResolvedValue([buildAccount()]);
    mockedCheckAccountControlPlaneReadiness.mockImplementation(() => pendingReadiness);
    vi.mocked(window.localStorage.getItem).mockImplementation((key: string) => {
      if (key === 'onboarding_v2_draft') return JSON.stringify(buildDraft());
      return null;
    });

    render(<OnboardingPage />);

    await screen.findByRole('button', { name: 'Verify Intake' });
    await userEvent.click(screen.getByRole('button', { name: 'Verify Intake' }));

    expect(await screen.findByText('Estimated progress')).toBeInTheDocument();
    expect(screen.getByText('Checking for recent intake in us-east-1...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Verifying intake 38%' })).toBeDisabled();
    expect(screen.getByRole('progressbar', { name: 'Verify intake progress' })).toHaveAttribute('aria-valuenow', '38');

    await act(async () => {
      resolveReadiness?.({
        account_id: '123456789012',
        stale_after_minutes: 30,
        overall_ready: true,
        missing_regions: [],
        regions: [],
      });
    });

    expect(await screen.findByRole('button', { name: 'Run final checks' })).toBeInTheDocument();
  });

  it('reuses the account-scoped synthetic event path after refresh when no revealed token is present', async () => {
    mockedUseAuth.mockReturnValue(buildAuthState(false));
    mockedGetAccounts.mockResolvedValue([buildAccount()]);
    vi.mocked(window.localStorage.getItem).mockImplementation((key: string) => {
      if (key === 'onboarding_v2_draft') return JSON.stringify(buildDraft());
      return null;
    });

    render(<OnboardingPage />);

    await screen.findByRole('button', { name: 'Verify Intake' });
    await userEvent.click(screen.getByRole('button', { name: 'Verify Intake' }));

    expect(mockedSendSyntheticControlPlaneEvent).not.toHaveBeenCalled();
    expect(mockedSendSyntheticControlPlaneEventForAccount).toHaveBeenCalledWith('123456789012', 'us-east-1');
    expect(await screen.findByRole('button', { name: 'Run final checks' })).toBeInTheDocument();
  });

  it('does not rotate implicitly when launching the control-plane stack with a hidden token', async () => {
    const rotateControlPlaneToken = vi.fn().mockResolvedValue('fresh-token');
    const buildControlPlaneForwarderLaunchStackUrl = vi
      .fn()
      .mockImplementation((_region: string, _stackName: string, tokenOverride?: string | null) =>
        tokenOverride ? `https://example.com/control-plane?token=${tokenOverride}` : null
      );
    mockedUseAuth.mockReturnValue({
      ...buildAuthState(false),
      rotateControlPlaneToken,
      buildControlPlaneForwarderLaunchStackUrl,
    });
    mockedGetAccounts.mockResolvedValue([buildAccount()]);
    vi.mocked(window.localStorage.getItem).mockImplementation((key: string) => {
      if (key === 'onboarding_v2_draft') return JSON.stringify(buildDraft());
      return null;
    });

    render(<OnboardingPage />);

    await screen.findByRole('button', { name: 'Launch CloudFormation' });
    await userEvent.click(screen.getByRole('button', { name: 'Launch CloudFormation' }));

    expect(rotateControlPlaneToken).not.toHaveBeenCalled();
    expect(buildControlPlaneForwarderLaunchStackUrl).not.toHaveBeenCalledWith(
      'us-east-1',
      'SecurityAutopilotControlPlaneForwarder',
      'fresh-token'
    );
    expect(window.open).not.toHaveBeenCalled();
    expect(
      await screen.findByText(
        'Token is hidden. Use Rotate Token explicitly, then relaunch CloudFormation and update the deployed forwarder stack.'
      )
    ).toBeInTheDocument();
  });

  it('rotates a token only from the explicit rotate control', async () => {
    const rotateControlPlaneToken = vi.fn().mockResolvedValue('fresh-token');
    mockedUseAuth.mockReturnValue({
      ...buildAuthState(false),
      rotateControlPlaneToken,
    });
    mockedGetAccounts.mockResolvedValue([buildAccount()]);
    vi.mocked(window.localStorage.getItem).mockImplementation((key: string) => {
      if (key === 'onboarding_v2_draft') return JSON.stringify(buildDraft());
      return null;
    });

    render(<OnboardingPage />);

    await screen.findByTitle('Rotate Token');
    await userEvent.click(screen.getByTitle('Rotate Token'));

    expect(rotateControlPlaneToken).toHaveBeenCalledTimes(1);
    expect(
      await screen.findByText(
        'Rotated control-plane token. Update any deployed forwarder stack before the previous token grace window expires.'
      )
    ).toBeInTheDocument();
  });

  it('resumes legacy access-analyzer drafts at final checks', async () => {
    mockedUseAuth.mockReturnValue(buildAuthState(false));
    mockedGetAccounts.mockResolvedValue([buildAccount()]);
    vi.mocked(window.localStorage.getItem).mockImplementation((key: string) => {
      if (key === 'onboarding_v2_draft') {
        return JSON.stringify(buildDraft({ step: 'access-analyzer' }));
      }
      return null;
    });

    render(<OnboardingPage />);

    expect(await screen.findByRole('button', { name: 'Run final checks' })).toBeInTheDocument();
    expect(screen.getAllByText('Final Connection Checks')).toHaveLength(2);
  });
});
