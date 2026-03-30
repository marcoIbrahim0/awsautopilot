'use client';

import { useRef } from 'react';
import { motion, useScroll, useTransform } from 'motion/react';
import { cn } from '@/lib/utils';

interface StickyScrollRevealProps {
  children: React.ReactNode;
  className?: string;
}

export function StickyScrollReveal({ children, className }: StickyScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end end'],
  });
  const opacity = useTransform(scrollYProgress, [0, 0.2, 0.8, 1], [0, 1, 1, 0]);
  const y = useTransform(scrollYProgress, [0, 0.2], [40, 0]);

  return (
    <div ref={ref} className={cn('relative', className)}>
      <div className="sticky top-24">
        <motion.div style={{ opacity, y }} className="will-change-transform">
          {children}
        </motion.div>
      </div>
    </div>
  );
}
