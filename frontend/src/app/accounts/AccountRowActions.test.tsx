import '@testing-library/jest-dom/vitest';

import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { AccountRowActions } from './AccountRowActions';

vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    className,
  }: {
    children: ReactNode;
    href: string;
    className?: string;
  }) => <a href={href} className={className}>{children}</a>,
}));

vi.mock('./AccountIngestActions', () => ({
  AccountIngestActions: () => <div>Ingest actions</div>,
}));

describe('AccountRowActions', () => {
  it('renders onboarding navigation without nested interactive elements', () => {
    const { container } = render(
      <AccountRowActions
        account={{
          id: 'acct-1',
          account_id: '123456789012',
          role_read_arn: 'arn:aws:iam::123456789012:role/SecurityAutopilotReadRole',
          role_write_arn: null,
          regions: ['us-east-1'],
          status: 'validated',
          created_at: '2026-03-20T00:00:00Z',
          updated_at: '2026-03-20T00:00:00Z',
          last_validated_at: '2026-03-20T00:00:00Z',
        }}
        onUpdate={vi.fn()}
      />,
    );

    expect(screen.getByRole('link', { name: 'Onboarding checks' })).toHaveAttribute('href', '/onboarding');
    expect(container.querySelector('a button, button a')).toBeNull();
  });
});
