export type RemediationOutcomeTone = 'success' | 'warning' | 'default';

export interface RemediationOutcomePresentation {
  canonicalLabel: string;
  canonicalValue: string;
  description: string;
  label: string;
  tone: RemediationOutcomeTone;
}

const PRESENTATION_BY_SUPPORT_TIER: Record<string, RemediationOutcomePresentation> = {
  deterministic_bundle: {
    canonicalLabel: 'Support tier',
    canonicalValue: 'deterministic_bundle',
    description: 'The platform can truthfully generate this bundle from the current inputs and runtime evidence.',
    label: 'Ready to generate',
    tone: 'success',
  },
  review_required_bundle: {
    canonicalLabel: 'Support tier',
    canonicalValue: 'review_required_bundle',
    description: 'The platform generated a truthful bundle, but an operator still needs to review the change before apply.',
    label: 'Needs review before apply',
    tone: 'warning',
  },
  manual_guidance_only: {
    canonicalLabel: 'Support tier',
    canonicalValue: 'manual_guidance_only',
    description:
      'The platform cannot truthfully generate a safe automatic bundle from the current evidence or inputs.',
    label: 'Manual steps required',
    tone: 'default',
  },
};

export function getRemediationOutcomePresentation(
  supportTier: string | null | undefined
): RemediationOutcomePresentation | null {
  if (!supportTier) return null;
  return PRESENTATION_BY_SUPPORT_TIER[supportTier] ?? null;
}
