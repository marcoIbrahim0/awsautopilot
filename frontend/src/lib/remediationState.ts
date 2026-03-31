export type RemediationStateVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';

export interface RemediationStatePresentation {
  label: string;
  description: string;
  variant: RemediationStateVariant;
}

type NoRemediationReason =
  | 'historical_resolved'
  | 'managed_on_account_scope'
  | 'managed_on_resource_scope'
  | 'no_current_remediation'
  | null
  | undefined;

const BUCKET_PRESENTATION: Record<string, RemediationStatePresentation> = {
  mixed: {
    label: 'Mixed remediation state',
    description:
      'This group contains findings in different remediation states. Open the PR bundle group for member-level status details.',
    variant: 'info',
  },
  resolved_without_run: {
    label: 'Resolved without new bundle run',
    description:
      'AWS source-of-truth checks now show this item as resolved, so no new PR bundle run is currently needed.',
    variant: 'success',
  },
  not_run_yet: {
    label: 'Not generated yet',
    description:
      'A remediation action exists for this item, but no PR bundle has been generated yet.',
    variant: 'default',
  },
  run_successful_pending_confirmation: {
    label: 'Generated, awaiting AWS verification',
    description:
      'A PR bundle was generated and run successfully, but AWS source-of-truth systems such as Security Hub have not confirmed closure yet.',
    variant: 'info',
  },
  run_successful_needs_followup: {
    label: 'Generated, needs follow-up',
    description:
      'A PR bundle was generated and run successfully, but this item still needs an additional follow-up change before it can fully resolve.',
    variant: 'warning',
  },
  run_successful_confirmed: {
    label: 'Generated and confirmed',
    description:
      'A PR bundle was generated and run successfully, and AWS source-of-truth checks now confirm the finding is resolved.',
    variant: 'success',
  },
  run_finished_metadata_only: {
    label: 'Needs review before apply',
    description:
      'The system produced review guidance or bundle artifacts for this item, but did not include runnable automatic changes.',
    variant: 'warning',
  },
  run_not_successful: {
    label: 'Generation/apply not successful',
    description:
      'A PR bundle was generated or attempted, but the run did not finish successfully.',
    variant: 'danger',
  },
};

export function getRemediationStatePresentation(
  bucket: string | null | undefined,
  hasRemediationAction = false,
  actionStatus?: string | null,
  statusMessage?: string | null
): RemediationStatePresentation | null {
  const normalized = (bucket || '').trim();
  const normalizedActionStatus = (actionStatus || '').trim().toLowerCase();
  if (normalized === 'mixed') {
    return {
      ...BUCKET_PRESENTATION.mixed,
      description: statusMessage?.trim() || BUCKET_PRESENTATION.mixed.description,
    };
  }
  if (normalizedActionStatus === 'resolved' && (!normalized || normalized === 'not_run_yet')) {
    return BUCKET_PRESENTATION.resolved_without_run;
  }
  if (normalized && BUCKET_PRESENTATION[normalized]) return BUCKET_PRESENTATION[normalized];
  if (hasRemediationAction) return BUCKET_PRESENTATION.not_run_yet;
  return null;
}

export function getNoRemediationActionPresentation(): RemediationStatePresentation {
  return getNoRemediationActionPresentationForReason();
}

export function getNoRemediationActionPresentationForReason(
  reason?: NoRemediationReason,
  scopeMessage?: string | null
): RemediationStatePresentation {
  if (reason === 'historical_resolved') {
    return {
      label: 'Resolved history',
      description:
        scopeMessage?.trim() ||
        'This finding is already resolved, so there is no current remediation action to generate.',
      variant: 'success',
    };
  }
  if (reason === 'managed_on_account_scope') {
    return {
      label: 'Managed at account scope',
      description:
        scopeMessage?.trim() ||
        'This finding family is remediated at account scope. Open the account-level row for the runnable fix.',
      variant: 'info',
    };
  }
  if (reason === 'managed_on_resource_scope') {
    return {
      label: 'Managed on resource rows',
      description:
        scopeMessage?.trim() ||
        'This finding family is remediated on affected resource rows. Open the resource-level row for the runnable fix.',
      variant: 'info',
    };
  }
  return {
    label: 'No remediation action yet',
    description:
      scopeMessage?.trim() ||
      'No runnable remediation action is linked to this row right now. If this finding family is managed on related rows, open those rows for the fix.',
    variant: 'default',
  };
}
