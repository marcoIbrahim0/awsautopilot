'use client';

import { cn } from '@/lib/utils';

interface SpotlightNewProps {
  className?: string;
  gradientFirst?: string;
  gradientSecond?: string;
  gradientThird?: string;
  translateY?: number;
  width?: number;
  height?: number;
  duration?: number;
}

/**
 * Spotlight New — Aceternity UI defaults (no modification).
 * Uses CSS spotlight-float animation for subtle motion.
 */
export function SpotlightNew({
  className,
  gradientFirst = 'radial-gradient(68.54% 68.72% at 55.02% 31.46%, hsla(210, 100%, 85%, .08) 0, hsla(210, 100%, 55%, .02) 50%, hsla(210, 100%, 45%, 0) 80%)',
  gradientSecond = 'radial-gradient(50% 50% at 50% 50%, hsla(210, 100%, 85%, .06) 0, hsla(210, 100%, 55%, .02) 80%, transparent 100%)',
  gradientThird = 'radial-gradient(50% 50% at 50% 50%, hsla(210, 100%, 85%, .04) 0, hsla(210, 100%, 45%, .02) 80%, transparent 100%)',
  translateY = -350,
  width = 560,
  height = 1380,
  duration = 7,
}: SpotlightNewProps) {
  return (
    <div
      className={cn('pointer-events-none absolute inset-0 z-[1] overflow-hidden', className)}
      aria-hidden
    >
      <div
        className="absolute opacity-90"
        style={{
          width: `${width}px`,
          height: `${height}px`,
          left: '50%',
          top: '50%',
          transform: `translate(-50%, calc(-50% + ${translateY}px))`,
          background: gradientFirst,
          animation: `spotlight-float ${duration}s ease-in-out infinite`,
        }}
      />
      <div
        className="absolute opacity-80"
        style={{
          width: `${width * 0.8}px`,
          height: `${height * 0.6}px`,
          left: '30%',
          top: '40%',
          background: gradientSecond,
          animation: `spotlight-float ${duration + 1}s ease-in-out infinite reverse`,
        }}
      />
      <div
        className="absolute opacity-70"
        style={{
          width: `${width * 0.6}px`,
          height: `${height * 0.5}px`,
          right: '20%',
          top: '50%',
          background: gradientThird,
          animation: `spotlight-float ${duration + 2}s ease-in-out infinite`,
        }}
      />
    </div>
  );
}
