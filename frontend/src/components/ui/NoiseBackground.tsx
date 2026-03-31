'use client';

import { type CSSProperties, useId } from 'react';

/**
 * Aceternity-style noise background: animated gradient + noise texture overlay.
 * @see https://ui.aceternity.com/components/noise-background
 */
interface NoiseBackgroundProps {
  children?: React.ReactNode;
  className?: string;
  containerClassName?: string;
  gradientColors?: string[];
  noiseIntensity?: number;
  speed?: number;
  backdropBlur?: boolean;
  animating?: boolean;
  style?: React.CSSProperties;
}

const DEFAULT_GRADIENT = [
  'rgb(10, 113, 255)',
  'rgb(5, 53, 119)',
  'rgb(10, 113, 255)',
];

export function NoiseBackground({
  children,
  className = '',
  containerClassName = '',
  gradientColors = DEFAULT_GRADIENT,
  noiseIntensity = 0.2,
  speed = 0.1,
  backdropBlur = false,
  animating = true,
  style,
}: NoiseBackgroundProps) {
  const id = useId().replace(/:/g, '');

  const gradientCss = gradientColors
    .map((c, i) => `${c} ${(i / (gradientColors.length - 1)) * 100}%`)
    .join(', ');

  return (
    <div
      className={`relative overflow-hidden ${containerClassName}`}
      style={
        {
          ...style,
          '--noise-opacity': noiseIntensity,
          '--gradient-colors': gradientCss,
          '--speed': speed,
        } as CSSProperties
      }
    >
      {/* Animated gradient */}
      <div
        className={`absolute inset-0 opacity-90 ${animating ? 'animate-gradient-shift' : ''}`}
        style={{
          backgroundImage: `linear-gradient(135deg, ${gradientCss})`,
          backgroundSize: animating ? '200% 200%' : '100% 100%',
          backgroundRepeat: 'no-repeat',
        }}
      />
      <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ opacity: `var(--noise-opacity)` }} aria-hidden>
        <filter id={`noise-${id}`}>
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.8"
            numOctaves="4"
            stitchTiles="stitch"
          />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#noise-${id})`} />
      </svg>
      {backdropBlur && <div className="absolute inset-0 backdrop-blur-sm" />}
      {children && (
        <div className={`relative z-10 ${className}`}>
          {children}
        </div>
      )}
    </div>
  );
}
