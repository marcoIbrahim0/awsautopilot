'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/lib/utils';

interface LayoutTextFlipProps {
  /** Static text before the flipping words (e.g. "Secure AWS ") */
  text?: string;
  /** Words/phrases that cycle (e.g. ["quickly.", "with confidence."]) */
  words: string[];
  className?: string;
  /** Duration in ms between word transitions */
  interval?: number;
}

export function LayoutTextFlip({
  text = '',
  words,
  className,
  interval = 3000,
}: LayoutTextFlipProps) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % words.length);
    }, interval);
    return () => clearInterval(id);
  }, [words.length, interval]);

  if (words.length === 0) return <>{text}</>;

  return (
    <span
      className={cn('inline-block overflow-hidden align-middle min-h-[1.2em]', className)}
      style={{ perspective: '200px' }}
    >
      {text}
      <span className="inline-block overflow-hidden align-middle min-h-[1.2em]">
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={words[index]}
            initial={{ rotateX: 0, opacity: 1 }}
            animate={{ rotateX: 0, opacity: 1 }}
            exit={{ rotateX: 90, opacity: 0 }}
            transition={{ duration: 0.25 }}
            style={{
              transformOrigin: '50% 50% -12px',
              display: 'inline-block',
              backfaceVisibility: 'hidden',
              transformStyle: 'preserve-3d',
            }}
            className="inline-block"
          >
            {words[index]}
          </motion.span>
        </AnimatePresence>
      </span>
    </span>
  );
}
