'use client';

import { useRef } from 'react';
import { motion, useScroll, useTransform } from 'motion/react';
import { cn } from '@/lib/utils';

interface CanvasRevealEffectProps {
  children: React.ReactNode;
  className?: string;
}

export function CanvasRevealEffect({ children, className }: CanvasRevealEffectProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  });
  const clipPath = useTransform(
    scrollYProgress,
    [0, 0.25, 0.5, 0.75, 1],
    [
      'inset(0 0 100% 0)',
      'inset(0 0 0% 0)',
      'inset(0 0 0% 0)',
      'inset(0 0 0% 0)',
      'inset(0 0 100% 0)',
    ]
  );

  return (
    <div ref={ref} className={cn('relative overflow-hidden', className)}>
      <motion.div
        className="pointer-events-none absolute inset-0 z-10 bg-bg"
        style={{ clipPath }}
      />
      <div className="relative z-0">{children}</div>
    </div>
  );
}
