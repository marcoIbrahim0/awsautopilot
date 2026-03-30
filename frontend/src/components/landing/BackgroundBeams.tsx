'use client';

import { cn } from '@/lib/utils';

interface BackgroundBeamsProps {
  className?: string;
  opacity?: number;
}

export function BackgroundBeams({ className, opacity = 0.15 }: BackgroundBeamsProps) {
  return (
    <div
      className={cn('pointer-events-none absolute inset-0 overflow-hidden', className)}
      aria-hidden
    >
      <svg
        className="absolute h-full w-full"
        style={{ opacity }}
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="beam-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0A71FF" stopOpacity="0.4" />
            <stop offset="50%" stopColor="#0A71FF" stopOpacity="0.1" />
            <stop offset="100%" stopColor="#0A71FF" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d="M0 200 Q 200 100 400 200 T 800 200 T 1200 200 V 800 H 0 Z"
          fill="url(#beam-gradient)"
          className="animate-beam-path"
        />
        <path
          d="M0 400 Q 300 300 600 400 T 1200 400 V 800 H 0 Z"
          fill="url(#beam-gradient)"
          className="animate-beam-path animation-delay-2000"
        />
        <path
          d="M0 600 Q 250 500 500 600 T 1000 600 V 800 H 0 Z"
          fill="url(#beam-gradient)"
          className="animate-beam-path animation-delay-4000"
        />
      </svg>
    </div>
  );
}
