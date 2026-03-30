import '@testing-library/jest-dom/vitest';

import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { NotificationCenterProvider, useNotificationCenter } from './NotificationCenterContext';

const mockJobs: Array<{
  id: string;
  type: 'findings';
  title: string;
  message: string;
  progress: number;
  status: 'running' | 'success';
  severity: 'info' | 'success';
  detail: string | null;
  bannerVisible: boolean;
  createdAt: number;
  updatedAt: number;
}> = [];

const getNotifications = vi.fn();
const patchNotificationState = vi.fn();
const upsertJobNotification = vi.fn();

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
  }),
}));

vi.mock('@/contexts/BackgroundJobsContext', () => ({
  useBackgroundJobs: () => ({
    jobs: mockJobs,
  }),
}));

vi.mock('@/lib/api', () => ({
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
  getNotifications: (...args: unknown[]) => getNotifications(...args),
  patchNotificationState: (...args: unknown[]) => patchNotificationState(...args),
  upsertJobNotification: (...args: unknown[]) => upsertJobNotification(...args),
}));

function Consumer() {
  const { items, unreadCount, markAllRead } = useNotificationCenter();
  return (
    <div>
      <button type="button" onClick={() => void markAllRead()}>
        Mark all read
      </button>
      <div data-testid="unread-count">{unreadCount}</div>
      <div data-testid="item-titles">{items.map((item) => item.title).join('|')}</div>
    </div>
  );
}

describe('NotificationCenterProvider', () => {
  beforeEach(() => {
    mockJobs.length = 0;
    getNotifications.mockReset();
    patchNotificationState.mockReset();
    upsertJobNotification.mockReset();
    vi.useRealTimers();
  });

  it('merges local jobs with persisted notifications and counts unread items', async () => {
    mockJobs.push({
      id: 'job-1',
      type: 'findings',
      title: 'Findings refresh',
      message: 'Refresh running.',
      progress: 50,
      status: 'running',
      severity: 'info',
      detail: null,
      bannerVisible: true,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    });
    getNotifications.mockResolvedValue({
      items: [
        {
          id: 'gov-1',
          kind: 'governance',
          source: 'governance',
          severity: 'warning',
          status: 'action_required',
          title: 'Approval needed',
          message: 'Review the remediation run.',
          detail: null,
          progress: null,
          action_url: '/actions/1',
          target_type: 'remediation_run',
          target_id: 'run-1',
          created_at: '2026-03-20T10:00:00Z',
          updated_at: '2026-03-20T10:00:00Z',
          read_at: null,
          archived_at: null,
        },
      ],
      total: 1,
      unread_total: 1,
    });
    upsertJobNotification.mockResolvedValue({});

    render(
      <NotificationCenterProvider>
        <Consumer />
      </NotificationCenterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('unread-count')).toHaveTextContent('2');
    });
    expect(screen.getByTestId('item-titles')).toHaveTextContent('Findings refresh');
    expect(screen.getByTestId('item-titles')).toHaveTextContent('Approval needed');
  });

  it('marks all items read optimistically', async () => {
    const user = userEvent.setup();
    getNotifications.mockResolvedValue({
      items: [
        {
          id: 'gov-1',
          kind: 'governance',
          source: 'governance',
          severity: 'warning',
          status: 'action_required',
          title: 'Approval needed',
          message: 'Review the remediation run.',
          detail: null,
          progress: null,
          action_url: '/actions/1',
          target_type: 'remediation_run',
          target_id: 'run-1',
          created_at: '2026-03-20T10:00:00Z',
          updated_at: '2026-03-20T10:00:00Z',
          read_at: null,
          archived_at: null,
        },
      ],
      total: 1,
      unread_total: 1,
    });
    patchNotificationState.mockResolvedValue({ updated: 1 });

    render(
      <NotificationCenterProvider>
        <Consumer />
      </NotificationCenterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('unread-count')).toHaveTextContent('1');
    });
    await user.click(screen.getByRole('button', { name: 'Mark all read' }));
    await waitFor(() => {
      expect(screen.getByTestId('unread-count')).toHaveTextContent('0');
    });
    expect(patchNotificationState).toHaveBeenCalledWith({ action: 'mark_all_read' });
  });

  it('syncs background jobs to the backend', async () => {
    vi.useFakeTimers();
    mockJobs.push({
      id: 'job-1',
      type: 'findings',
      title: 'Findings refresh',
      message: 'Refresh running.',
      progress: 50,
      status: 'running',
      severity: 'info',
      detail: null,
      bannerVisible: true,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    });
    getNotifications.mockResolvedValue({ items: [], total: 0, unread_total: 0 });
    upsertJobNotification.mockResolvedValue({});

    render(
      <NotificationCenterProvider>
        <Consumer />
      </NotificationCenterProvider>,
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });
    expect(upsertJobNotification).toHaveBeenCalledWith(
      'job-1',
      expect.objectContaining({
        status: 'running',
        title: 'Findings refresh',
      }),
    );
  });
});
