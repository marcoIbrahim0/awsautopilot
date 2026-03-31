import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

import { FindingCard } from './FindingCard';

const push = vi.fn();

vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));

const baseFinding = {
  id: 'f-1',
  finding_id: 'finding-1',
  tenant_id: 'tenant-1',
  account_id: '123456789012',
  region: 'us-east-1',
  source: 'security_hub',
  severity_label: 'HIGH',
  severity_normalized: 75,
  status: 'NOTIFIED',
  risk_acknowledged: true,
  risk_acknowledged_at: '2026-02-25T10:00:00Z',
  risk_acknowledged_by_user_id: 'user-1',
  risk_acknowledged_group_key: 'S3.1::AWS::S3::Bucket',
  in_scope: true,
  title: 'S3 bucket should block public access',
  description: null,
  resource_id: 'arn:aws:s3:::example-bucket',
  resource_type: 'AwsS3Bucket',
  control_id: 'S3.1',
  standard_name: null,
  first_observed_at: null,
  last_observed_at: null,
  updated_at: '2026-02-25T10:00:00Z',
  created_at: '2026-02-25T09:00:00Z',
  updated_at_db: '2026-02-25T10:00:00Z',
  remediation_action_id: null,
  remediation_action_type: null,
  remediation_action_status: null,
  remediation_action_account_id: null,
  remediation_action_region: null,
  remediation_action_group_id: null,
  remediation_action_group_status_bucket: null,
  remediation_action_group_latest_run_status: null,
  latest_pr_bundle_run_id: null,
  pending_confirmation: false,
  pending_confirmation_started_at: null,
  pending_confirmation_deadline_at: null,
  pending_confirmation_message: null,
  pending_confirmation_severity: null,
  status_message: null,
  status_severity: null,
  followup_kind: null,
};

describe('FindingCard risk acknowledgement rendering', () => {
  beforeEach(() => {
    push.mockReset();
  });

  it('shows the AWS service badge when the findings payload includes it', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          aws_service: 'Amazon EC2',
        }}
      />
    );

    expect(screen.getByText('Amazon EC2')).toBeInTheDocument();
  });

  it('shows the resource-scope handoff CTA when no direct action exists', async () => {
    const user = userEvent.setup();

    render(
      <FindingCard
        finding={{
          ...baseFinding,
          control_id: 'EC2.19',
          resource_type: 'AwsAccount',
          resource_id: 'AWS::::Account:123456789012',
          remediation_visibility_reason: 'managed_on_resource_scope',
          remediation_scope_owner: 'resource',
        }}
      />
    );

    const badge = screen.getByText('Fix on resource rows').closest('span');
    expect(badge).toHaveAttribute(
      'title',
      'This is a summary row. The runnable remediation lives on the affected resource rows for this control. Open those resource rows to generate the fix.'
    );
    expect(screen.getByRole('button', { name: 'Open actionable rows' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'View details' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Open actionable rows' }));

    expect(push).toHaveBeenCalledWith(
      '/findings?view=flat&account_id=123456789012&region=us-east-1&control_id=EC2.19&status=NOTIFIED&source=security_hub'
    );
  });

  it('shows risk acknowledged badge when finding is acknowledged', () => {
    render(<FindingCard finding={baseFinding} />);
    expect(screen.getByText('Risk acknowledged')).toBeInTheDocument();
  });

  it('keeps risk acknowledged badge visible after reload rerender', () => {
    const { rerender } = render(<FindingCard finding={baseFinding} />);
    expect(screen.getByText('Risk acknowledged')).toBeInTheDocument();

    rerender(
      <FindingCard
        finding={{
          ...baseFinding,
          status: 'NEW',
          updated_at: '2026-02-25T11:00:00Z',
          updated_at_db: '2026-02-25T11:00:00Z',
        }}
      />
    );

    expect(screen.getByText('Risk acknowledged')).toBeInTheDocument();
  });

  it('shows pending confirmation note when grouped execution succeeded but AWS confirmation is still pending', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          remediation_action_id: 'action-pending',
          remediation_action_group_id: 'group-1',
          remediation_action_group_status_bucket: 'run_successful_pending_confirmation',
          remediation_action_group_latest_run_status: 'finished',
          remediation_action_type: 'aws_config_enabled',
          remediation_action_status: 'open',
          remediation_action_account_id: '123456789012',
          status_message:
            'This fix was applied successfully. AWS source-of-truth checks like Security Hub can take up to 12 hours to confirm the finding is resolved.',
          status_severity: 'info',
        }}
      />
    );

    expect(
      screen.getByText(
        'This fix was applied successfully. AWS source-of-truth checks like Security Hub can take up to 12 hours to confirm the finding is resolved.'
      )
    ).toBeInTheDocument();
    expect(screen.getByText('Generated, awaiting AWS verification')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View PR bundle group' })).toHaveAttribute(
      'href',
      '/actions/group?group_id=group-1'
    );
  });

  it('shows metadata-only state and suppresses pending confirmation note for review-only outcomes', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          remediation_action_id: 'action-review',
          remediation_action_group_id: 'group-2',
          remediation_action_group_status_bucket: 'run_finished_metadata_only',
          remediation_action_group_latest_run_status: 'finished',
          status_message:
            'This fix was applied successfully. AWS source-of-truth checks like Security Hub can take up to 12 hours to confirm the finding is resolved.',
          status_severity: 'info',
        }}
      />
    );

    expect(screen.getByText('Needs review before apply')).toBeInTheDocument();
    expect(
      screen.queryByText(
        'This fix was applied successfully. AWS source-of-truth checks like Security Hub can take up to 12 hours to confirm the finding is resolved.'
      )
    ).not.toBeInTheDocument();
  });

  it('shows follow-up guidance for non-closing successful runs', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          remediation_action_id: 'action-followup',
          remediation_action_group_id: 'group-3',
          remediation_action_group_status_bucket: 'run_successful_needs_followup',
          remediation_action_group_latest_run_status: 'finished',
          status_message:
            'The fix was applied successfully. Restricted access was added, but unrestricted public access is still present. Remove the unrestricted rule to resolve this finding.',
          status_severity: 'warning',
          followup_kind: 'unrestricted_public_access_retained',
        }}
      />
    );

    expect(
      screen.getByText(
        'The fix was applied successfully. Restricted access was added, but unrestricted public access is still present. Remove the unrestricted rule to resolve this finding.'
      )
    ).toBeInTheDocument();
    expect(screen.getByText('Generated, needs follow-up')).toBeInTheDocument();
  });

  it('shows explicit confirmed remediation state when the grouped run is confirmed', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          remediation_action_id: 'action-1',
          remediation_action_group_status_bucket: 'run_successful_confirmed',
        }}
      />
    );

    const badge = screen.getByText('Generated and confirmed').closest('span');
    expect(badge).toHaveAttribute(
      'title',
      'A PR bundle was generated and run successfully, and AWS source-of-truth checks now confirm the finding is resolved.'
    );
  });

  it('shows explicit not-generated state when a remediation action exists but no run has started', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          remediation_action_id: 'action-2',
          remediation_action_type: 'pr_only',
          remediation_action_status: 'open',
        }}
      />
    );

    const badge = screen.getByText('Not generated yet').closest('span');
    expect(badge).toHaveAttribute(
      'title',
      'A remediation action exists for this item, but no PR bundle has been generated yet.'
    );
  });

  it('shows resolved-without-run when a remediation action is already closed by inventory truth', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          remediation_action_id: 'action-4',
          remediation_action_status: 'resolved',
          remediation_action_group_status_bucket: 'not_run_yet',
        }}
      />
    );

    const badge = screen.getByText('Resolved without new bundle run').closest('span');
    expect(badge).toHaveAttribute(
      'title',
      'AWS source-of-truth checks now show this item as resolved, so no new PR bundle run is currently needed.'
    );
    expect(screen.getByRole('button', { name: 'View action' })).toBeInTheDocument();
  });

  it('shows explicit failed remediation state when the grouped run did not finish successfully', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          remediation_action_id: 'action-3',
          remediation_action_group_status_bucket: 'run_not_successful',
        }}
      />
    );

    const badge = screen.getByText('Generation/apply not successful').closest('span');
    expect(badge).toHaveAttribute(
      'title',
      'A PR bundle was generated or attempted, but the run did not finish successfully.'
    );
  });

  it('shows a suppressed badge even when only workflow status indicates suppression', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          status: 'SUPPRESSED',
          effective_status: 'SUPPRESSED',
          exception_id: 'exc-1',
          exception_expires_at: null,
          exception_expired: false,
        }}
      />
    );

    expect(screen.getByText('Suppressed')).toBeInTheDocument();
  });

  it('shows remediation family copy when the finding control is mapped into a canonical family', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          control_id: 'EC2.19',
          control_family: {
            source_control_ids: ['EC2.19'],
            canonical_control_id: 'EC2.53',
            related_control_ids: ['EC2.53', 'EC2.13', 'EC2.18', 'EC2.19'],
            is_mapped: true,
          },
        }}
      />
    );

    expect(screen.getByText('EC2.19')).toBeInTheDocument();
    expect(screen.getByText('Remediation family: EC2.53')).toBeInTheDocument();
  });

  it('shows historical resolved copy instead of the generic no-action fallback', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          status: 'RESOLVED',
          effective_status: 'RESOLVED',
          remediation_visibility_reason: 'historical_resolved',
          remediation_scope_message:
            'This finding is already resolved, so there is no current remediation action to generate.',
        }}
      />
    );

    expect(screen.getByText('Resolved history')).toBeInTheDocument();
    expect(
      screen.getByText('This finding is already resolved, so there is no current remediation action to generate.')
    ).toBeInTheDocument();
  });

  it('shows account-scope copy for non-owner sibling rows', () => {
    render(
      <FindingCard
        finding={{
          ...baseFinding,
          remediation_visibility_reason: 'managed_on_account_scope',
          remediation_scope_owner: 'account',
          remediation_scope_message:
            'This finding family is remediated at account scope. Open the account-level row for the runnable fix.',
        }}
      />
    );

    expect(screen.getByText('Managed at account scope')).toBeInTheDocument();
    expect(
      screen.getByText(
        'This finding family is remediated at account scope. Open the account-level row for the runnable fix.'
      )
    ).toBeInTheDocument();
  });
});
