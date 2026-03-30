'use client';

import { AnimatedTooltip } from '@/components/ui/AnimatedTooltip';
import { Badge } from '@/components/ui/Badge';
import type { RemediationStatePresentation } from '@/lib/remediationState';

interface RemediationStateBadgeProps {
  presentation: RemediationStatePresentation;
}

export function RemediationStateBadge({ presentation }: RemediationStateBadgeProps) {
  return (
    <AnimatedTooltip
      content={presentation.description}
      placement="top"
      maxWidth="320px"
      delayMs={200}
      tapToToggle
      autoFlip
      focusable
    >
      <Badge variant={presentation.variant} title={presentation.description}>
        {presentation.label}
      </Badge>
    </AnimatedTooltip>
  );
}
