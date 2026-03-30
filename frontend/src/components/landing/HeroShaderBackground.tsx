'use client';

import { cn } from '@/lib/utils';

/**
 * Shader-style hero background inspired by Aceternity UI Shaders
 * (https://ui.aceternity.com/components/shaders).
 * Uses site colors: black base + accent blue (#0A71FF, #085ACC, #0F2E9B).
 * Lines gradient + subtle dot grid + soft spotlight, all CSS/SVG (no WebGL).
 */
interface HeroShaderBackgroundProps {
  className?: string;
}

const ACCENT = 'rgba(10, 113, 255, 0.4)';
const ACCENT_SOFT = 'rgba(10, 113, 255, 0.15)';
const ACCENT_DIM = 'rgba(10, 113, 255, 0.06)';
const DARK = 'rgba(5, 53, 119, 0.2)';

export function HeroShaderBackground({ className }: HeroShaderBackgroundProps) {
  return (
    <div
      className={cn(
        'pointer-events-none absolute inset-0 overflow-hidden bg-black',
        className
      )}
      aria-hidden
    >
      {/* Lines gradient – animated flowing lines in accent blue */}
      <svg
        className="absolute inset-0 h-full w-full opacity-70"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient
            id="shader-line-1"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="100%"
          >
            <stop offset="0%" stopColor={ACCENT_DIM} />
            <stop offset="50%" stopColor={ACCENT_SOFT} />
            <stop offset="100%" stopColor={ACCENT_DIM} />
          </linearGradient>
          <linearGradient
            id="shader-line-2"
            x1="100%"
            y1="0%"
            x2="0%"
            y2="100%"
          >
            <stop offset="0%" stopColor={ACCENT_DIM} />
            <stop offset="50%" stopColor={ACCENT} />
            <stop offset="100%" stopColor={ACCENT_DIM} />
          </linearGradient>
        </defs>
        <path
          d="M0 200 Q 300 100 600 200 T 1200 200 T 1800 200 V 800 H 0 Z"
          fill="url(#shader-line-1)"
          className="animate-shader-line-1"
        />
        <path
          d="M0 400 Q 400 300 800 400 T 1600 400 T 2400 400 V 800 H 0 Z"
          fill="url(#shader-line-2)"
          className="animate-shader-line-2"
        />
        <path
          d="M0 600 Q 250 500 500 600 T 1000 600 T 1500 600 V 800 H 0 Z"
          fill="url(#shader-line-1)"
          className="animate-shader-line-3"
        />
      </svg>

      {/* Dot grid – subtle distortion-style grid */}
      <div
        className="absolute inset-0 opacity-40"
        style={{
          backgroundImage: `
            radial-gradient(circle at 1px 1px, ${ACCENT_DIM} 1px, transparent 0)
          `,
          backgroundSize: '32px 32px',
          backgroundPosition: '0 0',
          animation: 'shader-dot-shift 20s linear infinite',
        }}
      />

      {/* Spotlight – soft radial gradient center */}
      <div
        className="absolute inset-0 opacity-90"
        style={{
          background: `radial-gradient(ellipse 80% 50% at 50% 20%, ${ACCENT_SOFT} 0%, transparent 50%),
                      radial-gradient(ellipse 60% 40% at 50% 80%, ${DARK} 0%, transparent 50%)`,
        }}
      />
    </div>
  );
}
