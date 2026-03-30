'use client';

import { motion } from 'motion/react';
import { cn } from '@/lib/utils';

interface BlurFadeInProps {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  duration?: number;
  inView?: boolean;
  viewportMargin?: string;
}

export function BlurFadeIn({
  children,
  className,
  delay = 0,
  duration = 0.4,
  inView = false,
  viewportMargin = '0px',
}: BlurFadeInProps) {
  const Comp = motion.div;
  return (
    <Comp
      initial={{ opacity: 0, filter: 'blur(10px)' }}
      animate={inView ? undefined : { opacity: 1, filter: 'blur(0px)' }}
      whileInView={inView ? { opacity: 1, filter: 'blur(0px)' } : undefined}
      viewport={inView ? { once: true, margin: viewportMargin } : undefined}
      transition={{ duration, delay }}
      className={cn(className)}
    >
      {children}
    </Comp>
  );
}
