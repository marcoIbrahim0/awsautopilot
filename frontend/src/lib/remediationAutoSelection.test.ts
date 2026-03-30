import { describe, expect, it } from 'vitest';

import { deriveAutoPrOnlySelection } from '@/lib/remediationAutoSelection';
import type { RemediationOptionsResponse } from '@/lib/api';

function makeOptions(overrides: Partial<RemediationOptionsResponse> = {}): RemediationOptionsResponse {
  return {
    action_id: 'action-1',
    action_type: 's3_bucket_access_logging',
    mode_options: ['pr_only'],
    strategies: [],
    recommendation: {
      mode: 'pr_only',
      default_mode: 'pr_only',
      advisory: true,
      enforced_by_policy: null,
      rationale: 'Use PR-only',
      matrix_position: {
        risk_tier: 'low',
        business_criticality: 'medium',
        cell: 'risk_low__criticality_medium',
      },
      evidence: {
        score: 28,
        context_incomplete: false,
        data_sensitivity: 0.65,
        internet_exposure: 0,
        privilege_level: 0,
        exploit_signals: 0,
        matched_signals: [],
      },
    },
    ...overrides,
  };
}

describe('deriveAutoPrOnlySelection', () => {
  it('derives a safe log bucket for deterministic alternate S3.9 profiles', () => {
    const result = deriveAutoPrOnlySelection(
      makeOptions({
        strategies: [
          {
            strategy_id: 's3_enable_access_logging_guided',
            label: 'Enable S3 access logging (guided)',
            mode: 'pr_only',
            risk_level: 'low',
            recommended: true,
            requires_inputs: true,
            input_schema: {
              fields: [
                {
                  key: 'log_bucket_name',
                  type: 'string',
                  required: true,
                  description: 'Destination log bucket.',
                  safe_default_value: 'security-autopilot-access-logs-{{account_id}}',
                },
              ],
            },
            dependency_checks: [
              {
                code: 's3_access_logging_bucket_scope_confirmed',
                status: 'pass',
                message: 'Bucket-scoped target was identified.',
              },
              {
                code: 's3_access_logging_destination_safety_unproven',
                status: 'fail',
                message: "Destination log bucket 'security-autopilot-access-logs-696505809372' could not be verified from this account context (404).",
              },
            ],
            warnings: ['Do not use the source bucket as the logging destination.'],
            supports_exception_flow: false,
            exception_only: false,
            profiles: [
              {
                profile_id: 's3_enable_access_logging_guided',
                support_tier: 'review_required_bundle',
                recommended: false,
                requires_inputs: true,
                supports_exception_flow: false,
                exception_only: false,
              },
              {
                profile_id: 's3_enable_access_logging_create_destination_bucket',
                support_tier: 'deterministic_bundle',
                recommended: true,
                requires_inputs: true,
                supports_exception_flow: false,
                exception_only: false,
              },
            ],
            recommended_profile_id: 's3_enable_access_logging_create_destination_bucket',
            missing_defaults: [],
            blocked_reasons: [
              "Destination log bucket 'security-autopilot-access-logs-696505809372' could not be verified from this account context (404).",
            ],
            preservation_summary: {
              source_bucket_scope_proven: true,
              destination_creation_planned: true,
            },
            decision_rationale: 'Create a dedicated destination bucket with secure defaults.',
          },
        ],
      }),
      '696505809372',
      'eu-north-1',
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.strategyId).toBe('s3_enable_access_logging_guided');
    expect(result.strategyInputs).toEqual({
      log_bucket_name: 'security-autopilot-access-logs-696505809372',
    });
  });
});
