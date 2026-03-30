import { render, screen } from '@testing-library/react';
import React from 'react';
import { vi } from 'vitest';

import { GroupedFindingsView } from './GroupedFindingsView';

vi.mock('motion/react', () => ({
  motion: {
    div: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('./FindingGroupCard', () => ({
  FindingGroupCard: ({ group }: { group: { group_key: string } }) => (
    <div data-testid="group-card">{group.group_key}</div>
  ),
}));

const baseGroup = {
  control_id: 'S3.1',
  rule_title: 'S3 buckets should block public access',
  resource_type: 'AWS::S3::Bucket',
  finding_count: 1,
  severity_distribution: {
    CRITICAL: 0,
    HIGH: 1,
    MEDIUM: 0,
    LOW: 0,
    INFORMATIONAL: 0,
  },
  risk_acknowledged: false,
  risk_acknowledged_count: 0,
  remediation_action_id: null,
  remediation_action_type: null,
  remediation_action_status: null,
  remediation_action_group_id: null,
  remediation_action_group_status_bucket: null,
  remediation_action_group_latest_run_status: null,
  pending_confirmation: false,
  pending_confirmation_started_at: null,
  pending_confirmation_deadline_at: null,
  pending_confirmation_message: null,
  pending_confirmation_severity: null,
  status_message: null,
  status_severity: null,
  followup_kind: null,
  is_shared_resource: false,
};

describe('GroupedFindingsView', () => {
  it('renders nested buckets for all selected grouping dimensions', () => {
    render(
      <GroupedFindingsView
        groupingDimensions={['severity', 'rule', 'region']}
        groups={[
          {
            ...baseGroup,
            group_key: 'S3.1|AWS::S3::Bucket|123456789012|us-east-1',
            account_ids: ['123456789012'],
            regions: ['us-east-1'],
          },
          {
            ...baseGroup,
            group_key: 'S3.1|AWS::S3::Bucket|123456789012|eu-north-1',
            account_ids: ['123456789012'],
            regions: ['eu-north-1'],
          },
        ]}
      />
    );

    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getByText('S3.1')).toBeInTheDocument();
    expect(screen.getByText('us-east-1')).toBeInTheDocument();
    expect(screen.getByText('eu-north-1')).toBeInTheDocument();
    expect(screen.getAllByTestId('group-card')).toHaveLength(2);
  });

  it('renders remediation grouping buckets in operator-value order', () => {
    const { container } = render(
      <GroupedFindingsView
        groupingDimensions={['remediation']}
        groups={[
          {
            ...baseGroup,
            group_key: 'ready',
            rule_title: 'Ready group',
            account_ids: ['123456789012'],
            regions: ['us-east-1'],
            remediation_action_id: 'action-ready',
            remediation_action_status: 'open',
            remediation_action_group_status_bucket: 'not_run_yet',
          },
          {
            ...baseGroup,
            group_key: 'review',
            rule_title: 'Review group',
            account_ids: ['123456789012'],
            regions: ['us-east-1'],
            remediation_action_id: 'action-review',
            remediation_action_status: 'open',
            remediation_action_group_status_bucket: 'run_finished_metadata_only',
          },
          {
            ...baseGroup,
            group_key: 'followup',
            rule_title: 'Follow-up group',
            account_ids: ['123456789012'],
            regions: ['us-east-1'],
            remediation_action_id: 'action-followup',
            remediation_action_status: 'open',
            remediation_action_group_status_bucket: 'run_successful_needs_followup',
          },
          {
            ...baseGroup,
            group_key: 'pending',
            rule_title: 'Pending group',
            account_ids: ['123456789012'],
            regions: ['us-east-1'],
            remediation_action_id: 'action-pending',
            remediation_action_status: 'open',
            remediation_action_group_status_bucket: 'run_successful_pending_confirmation',
          },
          {
            ...baseGroup,
            group_key: 'no-fix',
            rule_title: 'No fix group',
            account_ids: ['123456789012'],
            regions: ['us-east-1'],
            remediation_action_id: null,
            remediation_action_status: null,
            remediation_visibility_reason: 'managed_on_account_scope',
          },
        ]}
      />
    );

    const text = container.textContent || '';
    expect(screen.getByText('Ready to generate')).toBeInTheDocument();
    expect(screen.getByText('Needs review before apply')).toBeInTheDocument();
    expect(screen.getByText('Manual follow-up')).toBeInTheDocument();
    expect(screen.getByText('Awaiting AWS verification')).toBeInTheDocument();
    expect(screen.getByText('No runnable fix here')).toBeInTheDocument();
    expect(text.indexOf('Ready to generate')).toBeLessThan(text.indexOf('Needs review before apply'));
    expect(text.indexOf('Needs review before apply')).toBeLessThan(text.indexOf('Manual follow-up'));
    expect(text.indexOf('Manual follow-up')).toBeLessThan(text.indexOf('Awaiting AWS verification'));
    expect(text.indexOf('Awaiting AWS verification')).toBeLessThan(text.indexOf('No runnable fix here'));
  });
});
