'use client';

import { cn } from '@/lib/utils';

interface GlowingEffectProps {
  children: React.ReactNode;
  className?: string;
}

export function GlowingEffect({ children, className }: GlowingEffectProps) {
  return (
    <div
      className={cn(
        'relative rounded-xl border border-border bg-surface p-6',
        'before:absolute before:inset-0 before:rounded-xl before:opacity-0 before:transition-opacity before:duration-300',
        'before:shadow-[0_0_30px_rgba(10,113,255,0.12)]',
        'hover:before:opacity-100',
        className
      )}
    >
      {children}
    </div>
  );
}
