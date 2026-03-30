import { describe, expect, it } from 'vitest';

import type { ActionBusinessImpact } from '@/lib/api';
import { buildBusinessImpactPanel } from '@/components/actionDetailBusinessImpact';

function buildImpact(
  overrides: Partial<ActionBusinessImpact> = {},
): ActionBusinessImpact {
  return {
    technical_risk_score: 76,
    technical_risk_tier: 'high',
    criticality: {
      status: 'known',
      score: 15,
      tier: 'medium',
      weight: 2,
      explanation: 'Criticality scored 15 points from: Identity-boundary.',
      dimensions: [
        {
          dimension: 'identity_boundary',
          label: 'Identity-boundary',
          weight: 15,
          matched: true,
          contribution: 15,
          signals: ['resource_type:AwsAccount', 'keyword:root user'],
          explanation: 'Identity-boundary contributed 15 criticality points using: resource_type:AwsAccount, keyword:root user.',
        },
        {
          dimension: 'customer_facing',
          label: 'Customer-facing',
          weight: 25,
          matched: false,
          contribution: 0,
          signals: [],
          explanation: 'Customer-facing is explicit unknown for this action.',
        },
        {
          dimension: 'revenue_path',
          label: 'Revenue-path',
          weight: 25,
          matched: false,
          contribution: 0,
          signals: [],
          explanation: 'Revenue-path is explicit unknown for this action.',
        },
        {
          dimension: 'regulated_data',
          label: 'Regulated-data',
          weight: 25,
          matched: false,
          contribution: 0,
          signals: [],
          explanation: 'Regulated-data is explicit unknown for this action.',
        },
        {
          dimension: 'production_environment',
          label: 'Production-environment',
          weight: 10,
          matched: false,
          contribution: 0,
          signals: [],
          explanation: 'Production-environment is explicit unknown for this action.',
        },
      ],
    },
    matrix_position: {
      row: 'high',
      column: 'medium',
      cell: 'high:medium',
      risk_weight: 3,
      criticality_weight: 2,
      rank: 30276,
      explanation: 'Matrix row uses technical risk tier high; matrix column uses business criticality tier medium.',
    },
    summary: 'High technical risk intersects with Medium business criticality.',
    ...overrides,
  };
}

describe('buildBusinessImpactPanel', () => {
  it('translates identity-boundary matches into concise risk information', () => {
    const panel = buildBusinessImpactPanel(buildImpact(), 'iam_root_access_key_absent');

    expect(panel.riskSummary).toContain('high-risk issue affecting your shared access boundary');
    expect(panel.evidenceCards[0]).toMatchObject({
      title: 'Shared access boundary',
      dimension: 'identity_boundary',
    });
    expect(panel.evidenceCards[0]?.impact).toContain('affects IAM trust boundaries');
    expect(panel.nextStep).toContain('Immediately audit break-glass workflows');
    expect(panel.enrichmentPrompt).toBeNull();
  });

  it('provides enrichment prompt and score-driven summary when criticality is unknown', () => {
    const panel = buildBusinessImpactPanel(
      buildImpact({
        criticality: {
          status: 'unknown',
          score: 0,
          tier: 'unknown',
          weight: 1,
          explanation: 'Criticality remains explicit unknown.',
          dimensions: buildImpact().criticality.dimensions.map((dimension) => ({
            ...dimension,
            matched: false,
            contribution: 0,
            signals: [],
          })),
        },
      }),
      's3_block_public_access'
    );

    expect(panel.riskSummary).toContain('Business context is unverified');
    expect(panel.riskSummary).toContain('76/100');
    expect(panel.evidenceCards).toEqual([]);
    expect(panel.enrichmentPrompt).toContain('Tag this account');
    expect(panel.nextStep).toContain('Verify whether any S3 buckets in this account serve intentionally public content');
  });

  it('falls back to dimension-aware default guidance when action type is unknown', () => {
    const panel = buildBusinessImpactPanel(buildImpact(), 'unknown_action_type');
    expect(panel.nextStep).toContain('Confirm whether this account, role, or policy is shared');
  });
});

