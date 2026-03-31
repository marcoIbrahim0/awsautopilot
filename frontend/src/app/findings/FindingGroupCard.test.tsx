import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { FindingGroupCard } from './FindingGroupCard';
import { applyFindingGroupAction, getFindings } from '@/lib/api';

const push = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));

vi.mock('@/lib/api', () => ({
  getFindings: vi.fn(),
  applyFindingGroupAction: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}));

const mockedApplyFindingGroupAction = vi.mocked(applyFindingGroupAction);
const mockedGetFindings = vi.mocked(getFindings);

const baseGroup = {
  group_key: 'opaque-s3-bucket-group',
  control_id: 'S3.1',
  control_family: {
    source_control_ids: ['S3.1'],
    canonical_control_id: 'S3.1',
    related_control_ids: ['S3.1'],
    is_mapped: false,
  },
  rule_title: 'S3 buckets should block public access',
  resource_type: 'AWS::S3::Bucket',
  finding_count: 2,
  severity_distribution: {
    CRITICAL: 1,
    HIGH: 1,
    MEDIUM: 0,
    LOW: 0,
    INFORMATIONAL: 0,
  },
  account_ids: ['123456789012'],
  regions: ['us-east-1'],
  risk_acknowledged: false,
  risk_acknowledged_count: 0,
  remediation_action_id: null,
  remediation_action_type: null,
  remediation_action_status: null,
  remediation_action_group_id: null,
  pending_confirmation: false,
  pending_confirmation_started_at: null,
  pending_confirmation_deadline_at: null,
  pending_confirmation_message: null,
  pending_confirmation_severity: null,
};

describe('FindingGroupCard group actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetFindings.mockResolvedValue({ items: [], total: 0 });
  });

  it('routes suppress group to the exceptions screen with active filter context', async () => {
    const user = userEvent.setup();

    render(
      <FindingGroupCard
        group={baseGroup}
        effectiveTenantId="tenant-local"
        groupActionFilters={{
          account_id: '123456789012',
          region: 'us-east-1',
          severity: 'CRITICAL,HIGH',
          source: 'security_hub',
          status: 'NEW',
          control_id: 'S3.1',
          resource_id: 'arn:aws:s3:::example-bucket',
        }}
      />
    );

    expect(screen.queryByRole('button', { name: 'More actions' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Suppress Group' }));

    await waitFor(() => {
      expect(push).toHaveBeenCalledWith(
        '/exceptions?group_action=suppress&group_key=opaque-s3-bucket-group&control_id=S3.1&resource_type=AWS%3A%3AS3%3A%3ABucket&account_id=123456789012&region=us-east-1&severity=CRITICAL%2CHIGH&source=security_hub&status=NEW&resource_id=arn%3Aaws%3As3%3A%3A%3Aexample-bucket'
      );
    });
    expect(mockedApplyFindingGroupAction).not.toHaveBeenCalled();
  });

  it('shows mutation error when backend action fails', async () => {
    const user = userEvent.setup();
    mockedApplyFindingGroupAction.mockRejectedValue(new Error('Only admins can apply grouped findings actions.'));

    render(
      <FindingGroupCard
        group={baseGroup}
        effectiveTenantId="tenant-local"
      />
    );

    await user.click(screen.getByRole('button', { name: 'Acknowledge Risk' }));

    expect(await screen.findByText('Only admins can apply grouped findings actions.')).toBeInTheDocument();
  });

  it('keeps acknowledged-risk summary visible after reload rerender', () => {
    const { rerender } = render(
      <FindingGroupCard
        group={{
          ...baseGroup,
          risk_acknowledged: true,
          risk_acknowledged_count: 1,
        }}
        effectiveTenantId="tenant-local"
      />
    );

    expect(screen.getByText('1 acknowledged')).toBeInTheDocument();

    rerender(
      <FindingGroupCard
        group={{
          ...baseGroup,
          risk_acknowledged: true,
          risk_acknowledged_count: 2,
        }}
        effectiveTenantId="tenant-local"
      />
    );

    expect(screen.getByText('2 acknowledged')).toBeInTheDocument();
  });

  it('shows pending confirmation note on grouped cards in default findings view', () => {
    render(
      <FindingGroupCard
        group={{
          ...baseGroup,
          remediation_action_group_id: 'group-123',
          remediation_action_id: 'action-123',
          remediation_action_status: 'open',
          remediation_action_group_status_bucket: 'run_successful_pending_confirmation',
          status_message:
            'This fix was applied successfully. AWS source-of-truth checks like Security Hub can take up to 12 hours to confirm the finding is resolved.',
          status_severity: 'info',
        }}
        effectiveTenantId="tenant-local"
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
      '/actions/group?group_id=group-123'
    );
    expect(screen.getByRole('button', { name: 'Suppress Group' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Acknowledge Risk' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Mark False Positive' })).toBeInTheDocument();
  });

  it('shows explicit review-only remediation state on grouped cards', () => {
    render(
      <FindingGroupCard
        group={{
          ...baseGroup,
          remediation_action_id: 'action-review',
          remediation_action_status: 'open',
          remediation_action_group_status_bucket: 'run_finished_metadata_only',
          remediation_action_group_id: 'group-review',
          status_message: 'This message should stay hidden for metadata-only outcomes.',
          status_severity: 'info',
        }}
        effectiveTenantId="tenant-local"
      />
    );

    const badge = screen.getByText('Needs review before apply').closest('span');
    expect(badge).toHaveAttribute(
      'title',
      'The system produced review guidance or bundle artifacts for this item, but did not include runnable automatic changes.'
    );
    expect(screen.queryByText('This message should stay hidden for metadata-only outcomes.')).not.toBeInTheDocument();
  });

  it('shows explicit confirmed remediation state on grouped cards', () => {
    render(
      <FindingGroupCard
        group={{
          ...baseGroup,
          remediation_action_id: 'action-confirmed',
          remediation_action_status: 'resolved',
          remediation_action_group_status_bucket: 'run_successful_confirmed',
        }}
        effectiveTenantId="tenant-local"
      />
    );

    const badge = screen.getByText('Generated and confirmed').closest('span');
    expect(badge).toHaveAttribute(
      'title',
      'A PR bundle was generated and run successfully, and AWS source-of-truth checks now confirm the finding is resolved.'
    );
  });

  it('shows explicit failed remediation state on grouped cards', () => {
    render(
      <FindingGroupCard
        group={{
          ...baseGroup,
          remediation_action_id: 'action-failed',
          remediation_action_status: 'open',
          remediation_action_group_status_bucket: 'run_not_successful',
        }}
        effectiveTenantId="tenant-local"
      />
    );

    const badge = screen.getByText('Generation/apply not successful').closest('span');
    expect(badge).toHaveAttribute(
      'title',
      'A PR bundle was generated or attempted, but the run did not finish successfully.'
    );
  });

  it('shows a mixed remediation state summary when group members diverge', () => {
    render(
      <FindingGroupCard
        group={{
          ...baseGroup,
          remediation_action_id: 'action-mixed',
          remediation_action_status: 'open',
          remediation_action_group_status_bucket: 'mixed',
          status_message:
            'This group contains mixed remediation states: 13 generated and confirmed, 1 review-only, 1 resolved without a new bundle run, 1 not generated yet.',
        }}
        effectiveTenantId="tenant-local"
      />
    );

    const badge = screen.getByText('Mixed remediation state').closest('span');
    expect(badge).toHaveAttribute(
      'title',
      'This group contains mixed remediation states: 13 generated and confirmed, 1 review-only, 1 resolved without a new bundle run, 1 not generated yet.'
    );
    expect(screen.getByRole('button', { name: 'Generate PR Bundle' })).toBeInTheDocument();
  });

  it('loads expanded findings with the grouped card scope filters', async () => {
    const user = userEvent.setup();
    mockedGetFindings.mockResolvedValue({
      items: [],
      total: 0,
    });

    render(
      <FindingGroupCard
        group={baseGroup}
        effectiveTenantId="tenant-local"
      />
    );

    await user.click(screen.getByRole('button', { name: 'Expand findings' }));

    await waitFor(() => {
      expect(mockedGetFindings).toHaveBeenCalledWith(
        {
          control_id: 'S3.1',
          resource_type: 'AWS::S3::Bucket',
          account_id: '123456789012',
          region: 'us-east-1',
          limit: 50,
          offset: 0,
        },
        'tenant-local'
      );
    });
  });

  it('passes the active grouped status filter into expanded findings requests', async () => {
    const user = userEvent.setup();
    mockedGetFindings.mockResolvedValue({ items: [], total: 0 });

    render(
      <FindingGroupCard
        group={baseGroup}
        effectiveTenantId="tenant-local"
        groupActionFilters={{ status: 'NEW,NOTIFIED' }}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Expand findings' }));

    await waitFor(() => {
      expect(mockedGetFindings).toHaveBeenCalledWith(
        {
          control_id: 'S3.1',
          resource_type: 'AWS::S3::Bucket',
          account_id: '123456789012',
          region: 'us-east-1',
          status: 'NEW,NOTIFIED',
          limit: 50,
          offset: 0,
        },
        'tenant-local'
      );
    });
  });

  it('shows remediation family copy when the grouped finding rule maps to a canonical family', () => {
    render(
      <FindingGroupCard
        group={{
          ...baseGroup,
          control_id: 'EC2.19',
          control_family: {
            source_control_ids: ['EC2.19'],
            canonical_control_id: 'EC2.53',
            related_control_ids: ['EC2.53', 'EC2.13', 'EC2.18', 'EC2.19'],
            is_mapped: true,
          },
        }}
        effectiveTenantId="tenant-local"
      />
    );

    expect(screen.getByText('EC2.19')).toBeInTheDocument();
    expect(screen.getByText('Remediation family: EC2.53')).toBeInTheDocument();
  });

  it('shows resource-scope management copy instead of the generic fallback for non-owner rows', () => {
    render(
      <FindingGroupCard
        group={{
          ...baseGroup,
          control_id: 'EC2.19',
          remediation_visibility_reason: 'managed_on_resource_scope',
          remediation_scope_owner: 'resource',
        }}
        effectiveTenantId="tenant-local"
      />
    );

    expect(screen.getByText('Managed on resource rows')).toBeInTheDocument();
    expect(
      screen.getByText(
        'This finding family is remediated on affected resource rows. Open the resource-level row for the runnable fix.'
      )
    ).toBeInTheDocument();
  });
});
