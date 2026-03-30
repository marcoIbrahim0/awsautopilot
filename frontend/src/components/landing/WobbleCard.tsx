'use client';

import { useRef, useState } from 'react';
import { motion, useMotionTemplate, useMotionValue } from 'motion/react';
import { cn } from '@/lib/utils';

interface WobbleCardProps {
  children: React.ReactNode;
  className?: string;
  containerClassName?: string;
}

export function WobbleCard({ children, className, containerClassName }: WobbleCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const [isHovering, setHovering] = useState(false);

  const rotateX = useMotionTemplate`calc(${y}deg * 0.08)`;
  const rotateY = useMotionTemplate`calc(${x}deg * -0.08)`;

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const deltaX = (e.clientX - centerX) / (rect.width / 2);
    const deltaY = (e.clientY - centerY) / (rect.height / 2);
    x.set(deltaX * 8);
    y.set(deltaY * 8);
  }

  function handleMouseLeave() {
    x.set(0);
    y.set(0);
    setHovering(false);
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={handleMouseLeave}
      style={{
        rotateX: isHovering ? rotateX : 0,
        rotateY: isHovering ? rotateY : 0,
        transformStyle: 'preserve-3d',
      }}
      className={cn('perspective-[1000px]', containerClassName)}
    >
      <div
        className={cn(
          'rounded-xl border border-border bg-surface p-6 transition-shadow duration-200',
          isHovering && 'shadow-glow',
          className
        )}
      >
        {children}
      </div>
    </motion.div>
  );
}
