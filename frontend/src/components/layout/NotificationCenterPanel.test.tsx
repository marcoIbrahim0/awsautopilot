import '@testing-library/jest-dom/vitest';

import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { NotificationCenterPanel } from './NotificationCenterPanel';

vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    className,
    onClick,
  }: {
    children: ReactNode;
    href: string;
    className?: string;
    onClick?: () => void;
  }) => (
    <a href={href} className={className} onClick={onClick}>
      {children}
    </a>
  ),
}));

describe('NotificationCenterPanel', () => {
  it('splits active jobs from recent alerts and exposes archive only for read finished items', () => {
    render(
      <NotificationCenterPanel
        items={[
          {
            id: 'job-1',
            kind: 'job',
            source: 'background_job',
            severity: 'info',
            status: 'running',
            title: 'Findings refresh',
            message: 'Refresh running.',
            detail: null,
            progress: 55,
            action_url: null,
            target_type: null,
            target_id: null,
            client_key: 'job-1',
            created_at: '2026-03-20T10:00:00Z',
            updated_at: '2026-03-20T10:01:00Z',
            read_at: null,
            archived_at: null,
          },
          {
            id: 'gov-1',
            kind: 'governance',
            source: 'governance',
            severity: 'warning',
            status: 'action_required',
            title: 'Approval needed',
            message: 'Review the remediation run.',
            detail: 'Escalated to platform owner.',
            progress: null,
            action_url: '/actions/1',
            target_type: 'remediation_run',
            target_id: 'run-1',
            created_at: '2026-03-20T09:00:00Z',
            updated_at: '2026-03-20T09:05:00Z',
            read_at: '2026-03-20T09:06:00Z',
            archived_at: null,
          },
        ]}
        isLoading={false}
        error={null}
        unreadCount={1}
        onMarkAllRead={() => {}}
        onArchive={() => {}}
      />,
    );

    expect(screen.getByText('Active jobs')).toBeInTheDocument();
    expect(screen.getByText('Recent alerts')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open' })).toHaveAttribute('href', '/actions/1');
    expect(screen.getByRole('button', { name: 'Archive' })).toBeInTheDocument();
  });
});
