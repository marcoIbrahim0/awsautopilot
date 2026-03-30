import { render, screen, waitFor, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

import { RemediationRunProgress } from '@/components/RemediationRunProgress';
import { getRemediationRun, getRemediationRunExecution } from '@/lib/api';

vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock('motion/react', () => ({
  AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  motion: {
    div: ({
      children,
      initial: _initial,
      animate: _animate,
      transition: _transition,
      ...props
    }: {
      children?: ReactNode;
      initial?: unknown;
      animate?: unknown;
      transition?: unknown;
      [key: string]: unknown;
    }) => <div {...props}>{children}</div>,
  },
}));

vi.mock('@/components/ui/Badge', () => ({
  Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock('@/components/ui/Button', () => ({
  Button: ({ children, ...props }: { children: ReactNode; [key: string]: unknown }) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock('@/components/ui/Tabs', () => ({
  Tabs: () => <div>Tabs</div>,
}));

vi.mock('@/components/ui/MultiStepLoader', () => ({
  MultiStepLoader: () => <div>Loader</div>,
}));

vi.mock('@/lib/pr-bundle-download', () => ({
  downloadPrBundleZip: vi.fn(),
}));

vi.mock('@/lib/errorLogger', () => ({
  logError: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  cancelRemediationRun: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
  getRemediationRun: vi.fn(),
  getRemediationRunExecution: vi.fn(),
  resendRemediationRun: vi.fn(),
}));

const mockedGetRemediationRun = vi.mocked(getRemediationRun);
const mockedGetRemediationRunExecution = vi.mocked(getRemediationRunExecution);

describe('RemediationRunProgress', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockedGetRemediationRun.mockResolvedValue({
      id: 'run-1',
      action_id: 'action-1',
      mode: 'pr_only',
      status: 'success',
      outcome: 'Applied safely.',
      logs: 'pre-check\napply\npost-check',
      artifacts: {
        risk_snapshot: {
          checks: [{ code: 'review_complete', status: 'pass' }],
        },
      },
      approved_by_user_id: null,
      started_at: '2026-03-12T11:00:00Z',
      completed_at: '2026-03-12T11:05:00Z',
      created_at: '2026-03-12T10:59:00Z',
      updated_at: '2026-03-12T11:05:00Z',
      action: null,
      artifact_metadata: {
        implementation_artifacts: [
          {
            key: 'pr_payload',
            kind: 'pr_payload',
            label: 'Provider-agnostic PR payload',
            description: 'Repository metadata captured for downstream tooling.',
            href: '/remediation-runs/run-1#run-generated-files',
            executable: false,
            metadata: {},
          },
        ],
        evidence_pointers: [
          {
            key: 'risk_snapshot',
            kind: 'risk_snapshot',
            label: 'Dependency review snapshot',
            description: '1 dependency check captured for this run.',
            href: '/remediation-runs/run-1#run-generated-files',
            metadata: { check_count: 1 },
          },
          {
            key: 'activity_log',
            kind: 'activity_log',
            label: 'Run activity log',
            description: '3 execution log lines recorded for this run.',
            href: '/remediation-runs/run-1#run-activity',
            metadata: { line_count: 3 },
          },
        ],
        closure_checklist: [
          {
            id: 'evidence_attached',
            title: 'Evidence pointers attached',
            status: 'complete',
            detail: 'Evidence pointers are attached to this run.',
            evidence_keys: ['risk_snapshot', 'activity_log'],
          },
        ],
      },
    });
    mockedGetRemediationRunExecution.mockRejectedValue({ status: 404 });
  });

  it('keeps full-width run links actionable without rendering dead evidence buttons', async () => {
    const { container } = render(
      <RemediationRunProgress runId="run-1" fullWidth />
    );

    await waitFor(() => {
      expect(mockedGetRemediationRun).toHaveBeenCalledWith('run-1', undefined);
    });

    expect(screen.getByText('Bundle snapshot')).toBeInTheDocument();
    expect(screen.getByText('What you need to do', { selector: 'p' })).toBeInTheDocument();
    expect(screen.getByText('Closure proof', { selector: 'p' })).toBeInTheDocument();
    expect(screen.getByText('Review the bundle before apply')).toBeInTheDocument();
    expect(screen.getByText('Provider-agnostic PR payload')).toBeInTheDocument();
    expect(screen.getAllByText('Dependency review snapshot').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Evidence pointers attached').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Generation details').length).toBeGreaterThan(0);
    expect(screen.queryByText('Implementation artifacts')).not.toBeInTheDocument();

    expect(
      screen.getByRole('link', { name: 'Dependency review snapshot' })
    ).toHaveAttribute('href', '/remediation-runs/run-1#run-evidence-risk_snapshot');
    expect(
      screen.getByRole('link', { name: 'Run activity log' })
    ).toHaveAttribute('href', '/remediation-runs/run-1#run-activity');

    const riskSnapshotCard = container.querySelector('#run-evidence-risk_snapshot');
    const activityLogCard = container.querySelector('#run-evidence-activity_log');

    expect(riskSnapshotCard).not.toBeNull();
    expect(activityLogCard).not.toBeNull();
    expect(
      within(riskSnapshotCard as HTMLElement).queryByRole('link', { name: /Open evidence/i })
    ).not.toBeInTheDocument();
    expect(
      within(activityLogCard as HTMLElement).getByRole('link', { name: /Open evidence/i })
    ).toHaveAttribute('href', '/remediation-runs/run-1#run-activity');
  });

  it('shows a single full-width bundle progress heading', async () => {
    mockedGetRemediationRun.mockResolvedValueOnce({
      id: 'run-2',
      action_id: 'action-2',
      mode: 'pr_only',
      status: 'running',
      outcome: 'Generating bundle.',
      logs: 'queued\ngenerating',
      artifacts: {},
      approved_by_user_id: null,
      started_at: '2026-03-12T11:00:00Z',
      completed_at: null,
      created_at: '2026-03-12T10:59:00Z',
      updated_at: '2026-03-12T11:01:00Z',
      action: {
        id: 'action-2',
        title: 'Enable AWS Config',
        account_id: '123456789012',
        region: 'us-east-1',
        status: 'open',
      },
      artifact_metadata: {
        implementation_artifacts: [],
        evidence_pointers: [],
        closure_checklist: [],
      },
    } as never);

    render(<RemediationRunProgress runId="run-2" fullWidth />);

    await waitFor(() => {
      expect(mockedGetRemediationRun).toHaveBeenCalledWith('run-2', undefined);
    });

    expect(screen.getAllByText('Bundle progress')).toHaveLength(1);
  });

  it('does not render a second modal progress timeline for bundle generation', async () => {
    mockedGetRemediationRun.mockResolvedValueOnce({
      id: 'run-3',
      action_id: 'action-3',
      mode: 'pr_only',
      status: 'pending',
      outcome: 'Queued.',
      logs: 'queued',
      artifacts: {},
      approved_by_user_id: null,
      started_at: null,
      completed_at: null,
      created_at: '2026-03-12T10:59:00Z',
      updated_at: '2026-03-12T11:01:00Z',
      action: {
        id: 'action-3',
        title: 'Enable AWS Config',
        account_id: '123456789012',
        region: 'us-east-1',
        status: 'open',
      },
      artifact_metadata: {
        implementation_artifacts: [],
        evidence_pointers: [],
        closure_checklist: [],
      },
    } as never);

    render(<RemediationRunProgress runId="run-3" />);

    await waitFor(() => {
      expect(mockedGetRemediationRun).toHaveBeenCalledWith('run-3', undefined);
    });

    expect(screen.queryByText(/^Pending$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Running$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Complete$/)).not.toBeInTheDocument();
  });
});
