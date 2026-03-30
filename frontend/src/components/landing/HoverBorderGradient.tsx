'use client';

import { useState } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

interface HoverBorderGradientProps {
  children: React.ReactNode;
  href?: string;
  className?: string;
  containerClassName?: string;
  duration?: number;
  clockwise?: boolean;
  as?: 'button' | 'a';
  onClick?: () => void;
}

export function HoverBorderGradient({
  children,
  href,
  className,
  containerClassName,
  duration = 1,
  clockwise = true,
  as = 'a',
  onClick,
}: HoverBorderGradientProps) {
  const [hover, setHover] = useState(false);

  const borderStyle = {
    background: `conic-gradient(from 0deg, var(--accent), var(--accent-hover), var(--accent), var(--accent-hover))`,
    animation: hover
      ? `hover-border-rotate ${duration}s linear ${clockwise ? 'normal' : 'reverse'} infinite`
      : undefined,
  };

  const content = (
    <span
      className={cn(
        'relative z-10 flex items-center justify-center rounded-[calc(1rem-1px)] bg-bg px-4 py-2 text-sm font-medium text-muted transition-colors hover:text-text',
        className
      )}
    >
      {children}
    </span>
  );

  const wrapperClassName = cn(
    'relative inline-flex rounded-xl p-[1px] overflow-hidden',
    containerClassName
  );

  if (href) {
    return (
      <Link
        href={href}
        className={wrapperClassName}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
      >
        <span
          className="absolute inset-0 rounded-[inherit]"
          style={borderStyle}
          aria-hidden
        />
        {content}
      </Link>
    );
  }

  return (
    <button
      type="button"
      className={wrapperClassName}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onClick}
    >
      <span
        className="absolute inset-0 rounded-[inherit]"
        style={borderStyle}
        aria-hidden
      />
      {content}
    </button>
  );
}
