'use client';

import { useRef, useState, useEffect } from 'react';
import { motion, useScroll, useTransform } from 'motion/react';
import { cn } from '@/lib/utils';

interface TracingBeamStep {
  title: string;
  description: string;
}

interface TracingBeamProps {
  steps: TracingBeamStep[];
  className?: string;
}

export function TracingBeam({ steps, className }: TracingBeamProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end end'],
  });
  const [activeIndex, setActiveIndex] = useState(0);
  const beamHeight = useTransform(scrollYProgress, [0, 1], ['0%', '100%']);

  useEffect(() => {
    const unsubscribe = scrollYProgress.on('change', (v) => {
      const index = Math.min(Math.floor(v * steps.length), steps.length - 1);
      setActiveIndex(index >= 0 ? index : 0);
    });
    return () => unsubscribe();
  }, [scrollYProgress, steps.length]);

  return (
    <div ref={ref} className={cn('relative', className)}>
      <div className="absolute left-[11px] top-0 bottom-0 w-px bg-border" />
      <motion.div
        className="absolute left-[11px] top-0 w-px bg-accent origin-top"
        style={{ height: beamHeight }}
      />
      {steps.map((step, i) => (
        <div key={i} className="relative flex gap-6 pb-12 last:pb-0">
          <div
            className={cn(
              'absolute left-0 top-2 h-6 w-6 rounded-full border-2 flex items-center justify-center text-xs font-medium bg-bg z-10 transition-colors',
              activeIndex >= i ? 'border-accent bg-accent text-white' : 'border-border text-muted'
            )}
          >
            {i + 1}
          </div>
          <div className="pl-10">
            <h3 className="font-semibold text-text mb-1">{step.title}</h3>
            <p className="text-muted text-sm">{step.description}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
