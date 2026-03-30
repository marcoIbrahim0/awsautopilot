import type { RemediationOption } from '@/lib/api';

function recommendedProfile(strategy: RemediationOption | null) {
  const profiles = strategy?.profiles ?? [];
  if (profiles.length === 0) return null;
  const recommendedProfileId = (strategy?.recommended_profile_id || '').trim();
  return (
    profiles.find((profile) => profile.profile_id === recommendedProfileId)
    ?? profiles.find((profile) => profile.recommended)
    ?? null
  );
}

export function recommendedSupportTier(strategy: RemediationOption | null): string | null {
  return (recommendedProfile(strategy)?.support_tier || '').trim() || null;
}

export function allowsReviewBundleGeneration(strategy: RemediationOption | null): boolean {
  return recommendedSupportTier(strategy) === 'review_required_bundle';
}

export function allowsDeterministicAlternateGeneration(strategy: RemediationOption | null): boolean {
  const profile = recommendedProfile(strategy);
  if (!profile) return false;
  return (
    (profile.support_tier || '').trim() === 'deterministic_bundle'
    && profile.profile_id !== strategy?.strategy_id
  );
}

export function hasBlockingChecks(strategy: RemediationOption | null): boolean {
  const hasFailingChecks = (strategy?.dependency_checks ?? []).some((check) => check.status === 'fail');
  return (
    hasFailingChecks
    && !allowsReviewBundleGeneration(strategy)
    && !allowsDeterministicAlternateGeneration(strategy)
  );
}

export function strategyWarningMessages(strategy: RemediationOption | null): string[] {
  const includeFailingChecks =
    allowsReviewBundleGeneration(strategy) || allowsDeterministicAlternateGeneration(strategy);
  const checks = (strategy?.dependency_checks ?? []).filter((check) => {
    if (check.status === 'warn' || check.status === 'unknown') return true;
    if (includeFailingChecks && check.status === 'fail') return true;
    return false;
  });
  const warnings = strategy?.warnings ?? [];
  return [...checks.map((check) => check.message), ...warnings].filter(Boolean);
}

export function requiresRiskAcknowledgement(strategy: RemediationOption | null): boolean {
  return (strategy?.dependency_checks ?? []).some((check) => check.status === 'warn' || check.status === 'unknown');
}
