'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';

/**
 * Aceternity-style text hover effect: animates and outlines gradient on hover.
 * @see https://ui.aceternity.com/components/text-hover-effect
 * Uses site accent (#0A71FF) for gradient outline.
 */
interface TextHoverEffectAceternityProps {
  children: React.ReactNode;
  className?: string;
  /** Duration of the mask/gradient transition in seconds */
  duration?: number;
}

export function TextHoverEffectAceternity({
  children,
  className,
  duration = 0.3,
}: TextHoverEffectAceternityProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <span
      className={cn('inline-block cursor-default', className)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span
        className="relative inline-block transition-all"
        style={{
          transitionDuration: `${duration}s`,
          transitionTimingFunction: 'ease',
          background: hovered
            ? 'linear-gradient(135deg, #0A71FF 0%, #085ACC 50%, #0A71FF 100%)'
            : 'none',
          backgroundSize: '200% 200%',
          backgroundClip: hovered ? 'text' : undefined,
          WebkitBackgroundClip: hovered ? 'text' : undefined,
          WebkitTextFillColor: hovered ? 'transparent' : undefined,
          color: hovered ? undefined : 'inherit',
          backgroundPosition: hovered ? '100% 0' : '0 0',
          textShadow: hovered
            ? '0 0 20px rgba(10, 113, 255, 0.35), 0 0 40px rgba(10, 113, 255, 0.15)'
            : undefined,
        }}
      >
        {children}
      </span>
    </span>
  );
}
