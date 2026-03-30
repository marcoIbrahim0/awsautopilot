import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import ExportsPage from './page';

vi.mock('@/components/layout', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/components/ui/ButtonLink', () => ({
  ButtonLink: ({ children, href }: { children: ReactNode; href: string }) => <a href={href}>{children}</a>,
}));

vi.mock('@/app/settings/ExportsComplianceTab', () => ({
  ExportsComplianceTab: ({ panelId }: { panelId?: string }) => <div data-testid="exports-tab" data-panel-id={panelId}>Exports tab content</div>,
}));

describe('ExportsPage', () => {
  it('renders the exports workspace and links baseline report from the navbar route', () => {
    render(<ExportsPage />);

    expect(screen.getByRole('heading', { name: 'Exports' })).toBeInTheDocument();
    expect(screen.getByText('Exports tab content')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open baseline report' })).toHaveAttribute('href', '/settings?tab=baseline-report');
    expect(screen.getByTestId('exports-tab')).toHaveAttribute('data-panel-id', 'exports-panel');
  });
});
