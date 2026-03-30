import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { RootKeyRemediationLifecycle } from '@/components/root-key/RootKeyRemediationLifecycle';
import {
  completeRootKeyExternalTask,
  deleteRootKeyRemediationRun,
  disableRootKeyRemediationRun,
  getRootKeyRemediationRun,
  rollbackRootKeyRemediationRun,
  validateRootKeyRemediationRun,
} from '@/lib/api';
import type { RootKeyRunDetailResponse, RootKeyRunSnapshot } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  completeRootKeyExternalTask: vi.fn(),
  deleteRootKeyRemediationRun: vi.fn(),
  disableRootKeyRemediationRun: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
  getRootKeyRemediationRun: vi.fn(),
  rollbackRootKeyRemediationRun: vi.fn(),
  validateRootKeyRemediationRun: vi.fn(),
}));

const mockedCompleteTask = vi.mocked(completeRootKeyExternalTask);
const mockedDeleteRun = vi.mocked(deleteRootKeyRemediationRun);
const mockedDisableRun = vi.mocked(disableRootKeyRemediationRun);
const mockedGetRun = vi.mocked(getRootKeyRemediationRun);
const mockedRollbackRun = vi.mocked(rollbackRootKeyRemediationRun);
const mockedValidateRun = vi.mocked(validateRootKeyRemediationRun);

function buildRunDetail(overrides?: {
  unknownDependency?: boolean;
  state?: RootKeyRunSnapshot['state'];
}): RootKeyRunDetailResponse {
  const state: RootKeyRunSnapshot['state'] = overrides?.state ?? 'needs_attention';
  const unknownDependency = overrides?.unknownDependency ?? false;
  return {
    correlation_id: 'corr-1',
    contract_version: '2026-03-02',
    run: {
      id: 'run-1',
      account_id: '029037611564',
      region: 'eu-north-1',
      control_id: 'IAM.4',
      action_id: 'action-1',
      finding_id: 'finding-1',
      state,
      status: 'waiting_for_user',
      strategy_id: 'iam_root_key_disable',
      mode: 'manual',
      run_correlation_id: 'corr-1',
      retry_count: 0,
      lock_version: 1,
      rollback_reason: null,
      started_at: '2026-03-02T10:00:00Z',
      completed_at: null,
      created_at: '2026-03-02T10:00:00Z',
      updated_at: '2026-03-02T10:05:00Z',
    },
    external_tasks: [],
    dependencies: [
      {
        id: 'dep-1',
        run_id: 'run-1',
        fingerprint_type: 'root_key_usage_cloudtrail',
        fingerprint_hash: 'hash-1',
        status: unknownDependency ? 'unknown' : 'pass',
        unknown_dependency: unknownDependency,
        unknown_reason: unknownDependency ? 'unmanaged_cloudtrail_dependency' : null,
        fingerprint_payload: {
          service: 'iam.amazonaws.com',
          api_action: 'UpdateAccessKey',
          classification: unknownDependency ? 'unknown' : 'managed',
        },
        created_at: '2026-03-02T10:01:00Z',
        updated_at: '2026-03-02T10:01:00Z',
      },
    ],
    events: [
      {
        id: 'event-1',
        run_id: 'run-1',
        event_type: 'create_run',
        state: 'discovery',
        status: 'queued',
        rollback_reason: null,
        created_at: '2026-03-02T10:00:00Z',
        completed_at: null,
      },
      {
        id: 'event-2',
        run_id: 'run-1',
        event_type: 'mark_needs_attention',
        state,
        status: 'waiting_for_user',
        rollback_reason: null,
        created_at: '2026-03-02T10:04:00Z',
        completed_at: null,
      },
    ],
    artifacts: [
      {
        id: 'artifact-1',
        run_id: 'run-1',
        artifact_type: 'transition_evidence',
        state: 'discovery',
        status: 'ready',
        artifact_ref: 'https://example.com/evidence/discovery.json',
        artifact_sha256: 'sha-1',
        redaction_applied: true,
        created_at: '2026-03-02T10:00:10Z',
        completed_at: '2026-03-02T10:00:11Z',
      },
    ],
    event_count: 2,
    dependency_count: 1,
    artifact_count: 1,
  };
}

describe('RootKeyRemediationLifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedDeleteRun.mockResolvedValue({
      correlation_id: 'corr-delete',
      contract_version: '2026-03-02',
      idempotency_replayed: false,
      run: buildRunDetail().run,
    });
    mockedDisableRun.mockResolvedValue({
      correlation_id: 'corr-disable',
      contract_version: '2026-03-02',
      idempotency_replayed: false,
      run: buildRunDetail().run,
    });
    mockedValidateRun.mockResolvedValue({
      correlation_id: 'corr-validate',
      contract_version: '2026-03-02',
      idempotency_replayed: false,
      run: buildRunDetail().run,
    });
    mockedCompleteTask.mockResolvedValue({
      correlation_id: 'corr-task',
      contract_version: '2026-03-02',
      idempotency_replayed: false,
      run: buildRunDetail().run,
      task: {
        id: 'task-1',
        run_id: 'run-1',
        task_type: 'await_manual_validation',
        status: 'completed',
        due_at: null,
        completed_at: '2026-03-02T10:10:00Z',
        assigned_to_user_id: null,
        retry_count: 0,
        rollback_reason: null,
        created_at: '2026-03-02T10:00:00Z',
        updated_at: '2026-03-02T10:10:00Z',
      },
    });
  });

  it('renders timeline states, timestamps, and evidence link rows', async () => {
    mockedGetRun.mockResolvedValue(buildRunDetail());

    render(<RootKeyRemediationLifecycle runId="run-1" isAdmin={false} />);

    await waitFor(() => {
      expect(screen.getByText('Run Timeline')).toBeInTheDocument();
    });

    expect(screen.getByText('create_run')).toBeInTheDocument();
    expect(screen.getByText('mark_needs_attention')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'transition_evidence evidence' })).toHaveAttribute(
      'href',
      'https://example.com/evidence/discovery.json',
    );
  });

  it('executes unknown dependency wizard decision flow and triggers rollback transition', async () => {
    mockedGetRun.mockResolvedValue(buildRunDetail({ unknownDependency: true }));
    mockedRollbackRun.mockResolvedValue({
      correlation_id: 'corr-rollback',
      contract_version: '2026-03-02',
      idempotency_replayed: false,
      run: buildRunDetail({ unknownDependency: true }).run,
    });

    const user = userEvent.setup();
    render(<RootKeyRemediationLifecycle runId="run-1" isAdmin={true} />);

    await waitFor(() => {
      expect(screen.getByText('Action Required: Unknown Dependencies')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(
      screen.getByRole('checkbox', {
        name: /I reviewed unknown dependencies and accept that forward progress should remain fail-closed/i,
      }),
    );
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('radio', { name: 'Rollback run' }));
    await user.click(screen.getByRole('button', { name: 'Submit decision' }));

    await waitFor(() => {
      expect(mockedRollbackRun).toHaveBeenCalledTimes(1);
    });
  });

  it('renders API load errors and allows retry rendering path', async () => {
    mockedGetRun
      .mockRejectedValueOnce(new Error('Root-key API unavailable'))
      .mockResolvedValueOnce(buildRunDetail());

    const user = userEvent.setup();
    render(<RootKeyRemediationLifecycle runId="run-1" isAdmin={true} />);

    await waitFor(() => {
      expect(screen.getByText('Unable to load root-key remediation run')).toBeInTheDocument();
    });
    expect(screen.getByText('Root-key API unavailable')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Retry' }));

    await waitFor(() => {
      expect(screen.getByText('Run Timeline')).toBeInTheDocument();
    });
  });

  it('enforces read-only auth boundary for non-admin users', async () => {
    mockedGetRun.mockResolvedValue(buildRunDetail({ unknownDependency: true }));

    const user = userEvent.setup();
    render(<RootKeyRemediationLifecycle runId="run-1" isAdmin={false} />);

    await waitFor(() => {
      expect(screen.getByText('Read-only mode. Admin role is required for transitions and task completion.')).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: 'Rollback' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('button', { name: 'Submit decision' })).toBeDisabled();
  });
});
