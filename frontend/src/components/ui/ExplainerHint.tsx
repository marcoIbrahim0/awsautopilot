'use client';

import type { ReactNode } from 'react';

import { AnimatedTooltip, type AnimatedTooltipProps } from '@/components/ui/AnimatedTooltip';
import {
  getExplainerContent,
  type ExplainerConceptId,
  type ExplainerContext,
} from '@/components/operatorExplainers';
import { cn } from '@/lib/utils';

type ExplainerContentValue = ReactNode | { conceptId: ExplainerConceptId; context?: ExplainerContext };

export interface ExplainerHintProps {
  content: ExplainerContentValue;
  label?: string;
  iconOnly?: boolean;
  className?: string;
  triggerClassName?: string;
  placement?: AnimatedTooltipProps['placement'];
  maxWidth?: string;
}

function resolveExplainer(content: ExplainerContentValue) {
  if (typeof content === 'object' && content !== null && 'conceptId' in content) {
    return getExplainerContent(content.conceptId, content.context);
  }
  return { content };
}

export function ExplainerHint({
  content,
  label,
  iconOnly = false,
  className,
  triggerClassName,
  placement = 'top',
  maxWidth = '320px',
}: ExplainerHintProps) {
  const resolved = resolveExplainer(content);
  const accessibleLabel = label || resolved.label || 'this item';

  return (
    <AnimatedTooltip
      content={resolved.content}
      placement={placement}
      maxWidth={maxWidth}
      delayMs={250}
      tapToToggle
      autoFlip
      triggerClassName={triggerClassName}
    >
      <button
        type="button"
        aria-label="Show contextual help"
        title={`Show help for ${accessibleLabel}`}
        className={cn(
          'inline-flex items-center gap-1 rounded-full border border-border/65 bg-[var(--card-inset)] px-2 py-1 text-[11px] font-medium text-muted transition-colors hover:border-accent/25 hover:text-text focus:outline-none focus:ring-2 focus:ring-ring',
          iconOnly ? 'h-5 w-5 justify-center px-0 py-0 text-[10px]' : null,
          className,
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            'inline-flex items-center justify-center rounded-full border border-current/20 font-semibold leading-none',
            iconOnly ? 'h-5 w-5 text-[10px]' : 'h-4 w-4 text-[10px]',
          )}
        >
          i
        </span>
        {!iconOnly ? <span>{resolved.shortLabel ?? 'What is this?'}</span> : null}
      </button>
    </AnimatedTooltip>
  );
}
