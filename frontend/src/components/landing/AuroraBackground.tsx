'use client';

import { cn } from '@/lib/utils';

interface AuroraBackgroundProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
  className?: string;
  showRadialGradient?: boolean;
}

/**
 * Aurora Background — stock Aceternity UI.
 * Wraps children; gradient layers are absolute behind them.
 * Requires @keyframes aurora and .animate-aurora in globals.css.
 */
export function AuroraBackground({
  children,
  className,
  showRadialGradient = true,
  ...props
}: AuroraBackgroundProps) {
  return (
    <div
      className={cn('relative h-full w-full overflow-hidden', className)}
      {...props}
    >
      {/* Dark base so gradients are visible */}
      <div className="absolute inset-0 z-0 bg-black" />
      {/* Animated aurora layer — two gradients for keyframe (2 position values) */}
      <div
        className="absolute inset-0 z-0 h-full w-full animate-aurora"
        style={{
          background:
            'linear-gradient(135deg, rgba(10, 113, 255, 0.2) 0%, transparent 50%), linear-gradient(225deg, rgba(10, 113, 255, 0.15) 0%, transparent 50%)',
          backgroundSize: '200% 200%',
        }}
      />
      {showRadialGradient && (
        <div
          className="absolute inset-0 z-0 h-full w-full"
          style={{
            background:
              'radial-gradient(ellipse at 50% 0%, rgba(10, 113, 255, 0.08), transparent 60%), radial-gradient(ellipse at 50% 100%, rgba(10, 113, 255, 0.06), transparent 60%)',
          }}
        />
      )}
      {children}
    </div>
  );
}
