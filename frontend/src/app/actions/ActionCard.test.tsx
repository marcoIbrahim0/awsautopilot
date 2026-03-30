import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

import { ActionCard } from './ActionCard';
import type { ActionListItem } from '@/lib/api';

vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

const baseAction: ActionListItem = {
  id: 'action-1',
  action_type: 'sg_restrict_public_ports',
  target_id: 'target-1',
  account_id: '123456789012',
  region: 'us-east-1',
  score: 88,
  score_components: {
    severity: { normalized: 0.75, points: 26 },
    score: 88,
    business_impact: {
      summary: 'High technical risk intersects with medium business criticality.',
      technical_risk_score: 88,
      technical_risk_tier: 'high',
      criticality: {
        status: 'known',
        score: 20,
        tier: 'medium',
        weight: 2,
        dimensions: [],
        explanation: 'Business context is known.',
      },
      matrix_position: {
        row: 'high',
        column: 'medium',
        cell: 'high:medium',
        risk_weight: 3,
        criticality_weight: 2,
        rank: 10,
        explanation: 'High technical risk intersects with medium criticality.',
      },
    },
  },
  business_impact: {
    summary: 'High technical risk intersects with medium business criticality.',
    technical_risk_score: 88,
    technical_risk_tier: 'high',
    criticality: {
      status: 'known',
      score: 20,
      tier: 'medium',
      weight: 2,
      dimensions: [],
      explanation: 'Business context is known.',
    },
    matrix_position: {
      row: 'high',
      column: 'medium',
      cell: 'high:medium',
      risk_weight: 3,
      criticality_weight: 2,
      rank: 10,
      explanation: 'High technical risk intersects with medium criticality.',
    },
  },
  priority: 88,
  status: 'open',
  title: 'Restrict public admin ports',
  control_id: 'EC2.53',
  control_family: {
    source_control_ids: ['EC2.19', 'EC2.18'],
    canonical_control_id: 'EC2.53',
    related_control_ids: ['EC2.53', 'EC2.13', 'EC2.18', 'EC2.19'],
    is_mapped: true,
  },
  resource_id: 'sg-123',
  updated_at: '2026-03-26T10:00:00Z',
  finding_count: 2,
};

describe('ActionCard', () => {
  it('shows compact source-first control family mapping on action cards', () => {
    render(<ActionCard action={baseAction} />);

    expect(screen.getByText('EC2.19 +1 -> EC2.53')).toBeInTheDocument();
  });
});
