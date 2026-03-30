import { describe, expect, it } from 'vitest';

import {
  getNoRemediationActionPresentation,
  getNoRemediationActionPresentationForReason,
  getRemediationStatePresentation,
} from './remediationState';

describe('remediationState', () => {
  it('maps every grouped bucket to an explicit compact presentation', () => {
    expect(getRemediationStatePresentation('not_run_yet', true)).toEqual({
      label: 'Not generated yet',
      description:
        'A remediation action exists for this item, but no PR bundle has been generated yet.',
      variant: 'default',
    });
    expect(getRemediationStatePresentation('run_successful_pending_confirmation', true)).toEqual({
      label: 'Generated, awaiting AWS verification',
      description:
        'A PR bundle was generated and run successfully, but AWS source-of-truth systems such as Security Hub have not confirmed closure yet.',
      variant: 'info',
    });
    expect(getRemediationStatePresentation('run_successful_needs_followup', true)).toEqual({
      label: 'Generated, needs follow-up',
      description:
        'A PR bundle was generated and run successfully, but this item still needs an additional follow-up change before it can fully resolve.',
      variant: 'warning',
    });
    expect(getRemediationStatePresentation('run_successful_confirmed', true)).toEqual({
      label: 'Generated and confirmed',
      description:
        'A PR bundle was generated and run successfully, and AWS source-of-truth checks now confirm the finding is resolved.',
      variant: 'success',
    });
    expect(getRemediationStatePresentation('run_finished_metadata_only', true)).toEqual({
      label: 'Needs review before apply',
      description:
        'The system produced review guidance or bundle artifacts for this item, but did not include runnable automatic changes.',
      variant: 'warning',
    });
    expect(getRemediationStatePresentation('run_not_successful', true)).toEqual({
      label: 'Generation/apply not successful',
      description:
        'A PR bundle was generated or attempted, but the run did not finish successfully.',
      variant: 'danger',
    });
  });

  it('falls back to not-generated for remediation-backed rows with no bucket yet', () => {
    expect(getRemediationStatePresentation(null, true)).toEqual({
      label: 'Not generated yet',
      description:
        'A remediation action exists for this item, but no PR bundle has been generated yet.',
      variant: 'default',
    });
  });

  it('shows resolved-without-run when inventory closes an item before a new bundle is generated', () => {
    expect(getRemediationStatePresentation('not_run_yet', true, 'resolved')).toEqual({
      label: 'Resolved without new bundle run',
      description:
        'AWS source-of-truth checks now show this item as resolved, so no new PR bundle run is currently needed.',
      variant: 'success',
    });
  });

  it('shows a mixed remediation state for grouped rows with multiple member outcomes', () => {
    expect(
      getRemediationStatePresentation(
        'mixed',
        true,
        'open',
        'This group contains mixed remediation states: 13 generated and confirmed, 1 review-only, 1 resolved without a new bundle run, 1 not generated yet.'
      )
    ).toEqual({
      label: 'Mixed remediation state',
      description:
        'This group contains mixed remediation states: 13 generated and confirmed, 1 review-only, 1 resolved without a new bundle run, 1 not generated yet.',
      variant: 'info',
    });
  });

  it('returns a separate explicit state when no remediation action exists yet', () => {
    expect(getRemediationStatePresentation(null, false)).toBeNull();
    expect(getNoRemediationActionPresentation()).toEqual({
      label: 'No remediation action yet',
      description:
        'No remediation action is currently available for this item, usually because dependency or safety checks blocked generation.',
      variant: 'default',
    });
  });

  it('returns explicit history and sibling-scope copy for no-action rows with visibility metadata', () => {
    expect(getNoRemediationActionPresentationForReason('historical_resolved')).toEqual({
      label: 'Resolved history',
      description:
        'This finding is already resolved, so there is no current remediation action to generate.',
      variant: 'success',
    });
    expect(getNoRemediationActionPresentationForReason('managed_on_account_scope')).toEqual({
      label: 'Managed at account scope',
      description:
        'This finding family is remediated at account scope. Open the account-level row for the runnable fix.',
      variant: 'info',
    });
    expect(getNoRemediationActionPresentationForReason('managed_on_resource_scope')).toEqual({
      label: 'Managed on resource rows',
      description:
        'This finding family is remediated on affected resource rows. Open the resource-level row for the runnable fix.',
      variant: 'info',
    });
  });
});
