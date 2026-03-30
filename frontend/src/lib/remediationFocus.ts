import type { Finding, FindingGroup, RemediationVisibilityReason } from '@/lib/api';

export type RemediationFocusBucket =
  | 'ready_to_generate'
  | 'needs_review'
  | 'manual_follow_up'
  | 'awaiting_aws_verification'
  | 'no_runnable_fix'
  | 'resolved_or_other';

export interface RemediationFocusPresentation {
  description: string;
  key: RemediationFocusBucket;
  label: string;
}

type RemediationFocusInput = {
  effectiveStatus?: string | null;
  followupKind?: string | null;
  pendingConfirmation?: boolean;
  remediationActionId?: string | null;
  remediationActionStatus?: string | null;
  remediationActionGroupStatusBucket?: string | null;
  remediationVisibilityReason?: RemediationVisibilityReason | null;
};

const PRESENTATION: Record<RemediationFocusBucket, RemediationFocusPresentation> = {
  ready_to_generate: {
    key: 'ready_to_generate',
    label: 'Ready to generate',
    description: 'A runnable PR-bundle path is available now.',
  },
  needs_review: {
    key: 'needs_review',
    label: 'Needs review before apply',
    description: 'Bundle guidance exists, but operator review is still required.',
  },
  manual_follow_up: {
    key: 'manual_follow_up',
    label: 'Manual follow-up',
    description: 'A generated run exists, but another operator step is still required.',
  },
  awaiting_aws_verification: {
    key: 'awaiting_aws_verification',
    label: 'Awaiting AWS verification',
    description: 'The run finished, but AWS source-of-truth confirmation is still pending.',
  },
  no_runnable_fix: {
    key: 'no_runnable_fix',
    label: 'No runnable fix here',
    description: 'This row does not currently expose a runnable remediation path.',
  },
  resolved_or_other: {
    key: 'resolved_or_other',
    label: 'Resolved / other',
    description: 'This row is already resolved or does not need immediate remediation work.',
  },
};

export const REMEDIATION_FOCUS_ORDER: RemediationFocusBucket[] = [
  'ready_to_generate',
  'needs_review',
  'manual_follow_up',
  'awaiting_aws_verification',
  'no_runnable_fix',
  'resolved_or_other',
];

function isResolvedStatus(value: string | null | undefined): boolean {
  return (value || '').trim().toUpperCase() === 'RESOLVED';
}

function classifyRemediationFocus(input: RemediationFocusInput): RemediationFocusBucket {
  const bucket = (input.remediationActionGroupStatusBucket || '').trim();
  const actionStatus = (input.remediationActionStatus || '').trim().toLowerCase();

  if (bucket === 'run_successful_pending_confirmation' || input.pendingConfirmation) {
    return 'awaiting_aws_verification';
  }
  if (bucket === 'run_successful_needs_followup' || Boolean(input.followupKind)) {
    return 'manual_follow_up';
  }
  if (bucket === 'run_finished_metadata_only') {
    return 'needs_review';
  }
  if (
    input.remediationActionId &&
    actionStatus === 'open' &&
    (!bucket || bucket === 'not_run_yet')
  ) {
    return 'ready_to_generate';
  }
  if (
    input.remediationVisibilityReason === 'managed_on_account_scope' ||
    input.remediationVisibilityReason === 'managed_on_resource_scope' ||
    !input.remediationActionId
  ) {
    return 'no_runnable_fix';
  }
  if (
    input.remediationVisibilityReason === 'historical_resolved' ||
    isResolvedStatus(input.remediationActionStatus) ||
    isResolvedStatus(input.effectiveStatus)
  ) {
    return 'resolved_or_other';
  }
  return 'resolved_or_other';
}

export function getRemediationFocusPresentation(
  bucket: RemediationFocusBucket
): RemediationFocusPresentation {
  return PRESENTATION[bucket];
}

export function classifyFindingRemediationFocus(finding: Finding): RemediationFocusBucket {
  return classifyRemediationFocus({
    effectiveStatus: finding.effective_status || finding.status,
    followupKind: finding.followup_kind,
    pendingConfirmation: finding.pending_confirmation,
    remediationActionId: finding.remediation_action_id,
    remediationActionStatus: finding.remediation_action_status,
    remediationActionGroupStatusBucket: finding.remediation_action_group_status_bucket,
    remediationVisibilityReason: finding.remediation_visibility_reason,
  });
}

export function classifyFindingGroupRemediationFocus(group: FindingGroup): RemediationFocusBucket {
  return classifyRemediationFocus({
    followupKind: group.followup_kind,
    pendingConfirmation: group.pending_confirmation,
    remediationActionId: group.remediation_action_id,
    remediationActionStatus: group.remediation_action_status,
    remediationActionGroupStatusBucket: group.remediation_action_group_status_bucket,
    remediationVisibilityReason: group.remediation_visibility_reason,
  });
}
