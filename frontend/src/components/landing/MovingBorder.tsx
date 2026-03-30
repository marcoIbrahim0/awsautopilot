'use client';

import { cn } from '@/lib/utils';

interface MovingBorderProps {
  children: React.ReactNode;
  className?: string;
  containerClassName?: string;
  borderClassName?: string;
  borderRadius?: string;
  duration?: number;
}

export function MovingBorder({
  children,
  className,
  containerClassName,
  borderClassName,
  borderRadius = '1rem',
  duration = 3000,
}: MovingBorderProps) {
  return (
    <div
      className={cn('relative overflow-hidden', containerClassName)}
      style={{ borderRadius }}
    >
      <div
        className={cn(
          'absolute inset-[-1px] z-0 rounded-[inherit] moving-border-layer',
          borderClassName
        )}
        style={{
          background:
            'linear-gradient(90deg, transparent 0%, rgba(10,113,255,0.25) 25%, rgba(10,113,255,0.4) 50%, rgba(10,113,255,0.25) 75%, transparent 100%)',
          backgroundSize: '200% 100%',
          animation: `moving-border ${duration}ms linear infinite`,
        }}
      />
      <div
        className={cn(
          'relative z-10 m-[1px] rounded-[inherit] bg-bg min-h-0',
          className
        )}
        style={{ borderRadius: 'calc(1rem - 1px)' }}
      >
        {children}
      </div>
    </div>
  );
}
