'use client';

import { useRef, useState, useCallback } from 'react';
import { motion } from 'motion/react';
import { cn } from '@/lib/utils';

interface MagneticButtonProps {
  children: React.ReactNode;
  className?: string;
  /** Max translate in px (default 8). Use when wrapping in Link. */
  strength?: number;
}

export function MagneticButton({
  children,
  className,
  strength = 8,
}: MagneticButtonProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLSpanElement>) => {
      if (!ref.current) return;
      const rect = ref.current.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const deltaX = (e.clientX - centerX) / rect.width;
      const deltaY = (e.clientY - centerY) / rect.height;
      const x = Math.max(-1, Math.min(1, deltaX)) * strength;
      const y = Math.max(-1, Math.min(1, deltaY)) * strength;
      setPosition({ x, y });
    },
    [strength]
  );

  const handleMouseLeave = useCallback(() => {
    setPosition({ x: 0, y: 0 });
  }, []);

  return (
    <motion.span
      ref={ref}
      role="button"
      tabIndex={0}
      className={cn(
        'inline-flex cursor-pointer items-center justify-center rounded-xl px-5 py-2.5 text-base font-medium text-white transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-bg',
        'bg-primary-btn-bg hover:bg-primary-btn-hover',
        className
      )}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      animate={{ x: position.x, y: position.y }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      {children}
    </motion.span>
  );
}
