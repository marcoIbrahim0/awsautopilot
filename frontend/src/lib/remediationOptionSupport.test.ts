import { describe, expect, it } from 'vitest';

import {
  allowsDeterministicAlternateGeneration,
  allowsReviewBundleGeneration,
  hasBlockingChecks,
  requiresRiskAcknowledgement,
  strategyWarningMessages,
} from '@/lib/remediationOptionSupport';
import type { RemediationOption } from '@/lib/api';

function makeStrategy(overrides: Partial<RemediationOption> = {}): RemediationOption {
  return {
    strategy_id: 'config_enable_account_local_delivery',
    label: 'Test strategy',
    mode: 'pr_only',
    risk_level: 'low',
    recommended: true,
    requires_inputs: false,
    input_schema: { fields: [] },
    dependency_checks: [],
    warnings: [],
    supports_exception_flow: false,
    exception_only: false,
    ...overrides,
  };
}

describe('remediationOptionSupport', () => {
  it('allows review bundle generation despite failing dependency checks', () => {
    const strategy = makeStrategy({
      dependency_checks: [
        {
          code: 'access_path_evidence_unavailable',
          status: 'fail',
          message: 'Unable to inspect bucket website configuration (AccessDenied).',
        },
      ],
      profiles: [
        {
          profile_id: 's3_bucket_block_public_access_standard',
          support_tier: 'review_required_bundle',
          recommended: false,
        },
        {
          profile_id: 's3_bucket_block_public_access_review_state_verification',
          support_tier: 'review_required_bundle',
          recommended: true,
        },
      ],
      recommended_profile_id: 's3_bucket_block_public_access_review_state_verification',
    });

    expect(allowsReviewBundleGeneration(strategy)).toBe(true);
    expect(hasBlockingChecks(strategy)).toBe(false);
    expect(strategyWarningMessages(strategy)).toContain(
      'Unable to inspect bucket website configuration (AccessDenied).'
    );
  });

  it('still requires acknowledgement when review-only generation carries warning-level checks', () => {
    const strategy = makeStrategy({
      dependency_checks: [
        {
          code: 's3_public_access_dependency',
          status: 'warn',
          message: 'Validate direct bucket access dependencies before applying this strategy.',
        },
        {
          code: 'access_path_evidence_unavailable',
          status: 'fail',
          message: 'Unable to inspect bucket website configuration (AccessDenied).',
        },
      ],
      profiles: [
        {
          profile_id: 's3_bucket_block_public_access_review_state_verification',
          support_tier: 'review_required_bundle',
          recommended: true,
        },
      ],
      recommended_profile_id: 's3_bucket_block_public_access_review_state_verification',
    });

    expect(allowsReviewBundleGeneration(strategy)).toBe(true);
    expect(hasBlockingChecks(strategy)).toBe(false);
    expect(requiresRiskAcknowledgement(strategy)).toBe(true);
  });

  it('keeps executable strategies blocked when dependency checks fail', () => {
    const strategy = makeStrategy({
      strategy_id: 's3_bucket_access_logging_existing_destination',
      dependency_checks: [
        {
          code: 'destination_bucket_missing',
          status: 'fail',
          message: 'Destination log bucket could not be verified.',
        },
      ],
      profiles: [
        {
          profile_id: 's3_bucket_access_logging_existing_destination',
          support_tier: 'deterministic_bundle',
          recommended: true,
        },
      ],
      recommended_profile_id: 's3_bucket_access_logging_existing_destination',
    });

    expect(allowsReviewBundleGeneration(strategy)).toBe(false);
    expect(allowsDeterministicAlternateGeneration(strategy)).toBe(false);
    expect(hasBlockingChecks(strategy)).toBe(true);
    expect(strategyWarningMessages(strategy)).not.toContain(
      'Destination log bucket could not be verified.'
    );
  });

  it('allows deterministic alternate profile generation when the recommended profile changes branches', () => {
    const strategy = makeStrategy({
      strategy_id: 's3_enable_access_logging_guided',
      dependency_checks: [
        {
          code: 's3_access_logging_destination_safety_unproven',
          status: 'fail',
          message: "Destination log bucket 'security-autopilot-access-logs-696505809372' could not be verified from this account context (404).",
        },
      ],
      profiles: [
        {
          profile_id: 's3_enable_access_logging_guided',
          support_tier: 'review_required_bundle',
          recommended: false,
        },
        {
          profile_id: 's3_enable_access_logging_create_destination_bucket',
          support_tier: 'deterministic_bundle',
          recommended: true,
        },
      ],
      recommended_profile_id: 's3_enable_access_logging_create_destination_bucket',
    });

    expect(allowsReviewBundleGeneration(strategy)).toBe(false);
    expect(allowsDeterministicAlternateGeneration(strategy)).toBe(true);
    expect(hasBlockingChecks(strategy)).toBe(false);
    expect(strategyWarningMessages(strategy)).toContain(
      "Destination log bucket 'security-autopilot-access-logs-696505809372' could not be verified from this account context (404)."
    );
  });
});
