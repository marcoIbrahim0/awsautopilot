'use client';

import { cn } from '@/lib/utils';

interface TextHoverEffectProps {
  children: React.ReactNode;
  className?: string;
  as?: 'span' | 'p' | 'div';
}

export function TextHoverEffect({
  children,
  className,
  as: Tag = 'span',
}: TextHoverEffectProps) {
  return (
    <Tag
      className={cn(
        'inline-block transition-all duration-200',
        'hover:scale-105 hover:text-accent',
        'cursor-default',
        className
      )}
    >
      {children}
    </Tag>
  );
}
