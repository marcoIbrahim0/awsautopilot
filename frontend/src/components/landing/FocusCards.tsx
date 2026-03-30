'use client';

import { useState } from 'react';
import { motion } from 'motion/react';
import { cn } from '@/lib/utils';

interface FocusCardItem {
  title: string;
  description: string;
  image?: string;
}

interface FocusCardsProps {
  cards: FocusCardItem[];
  className?: string;
}

export function FocusCards({ cards, className }: FocusCardsProps) {
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null);

  return (
    <div
      className={cn('grid gap-4 sm:grid-cols-2 lg:grid-cols-3', className)}
      onMouseLeave={() => setFocusedIndex(null)}
    >
      {cards.map((card, i) => (
        <motion.div
          key={card.title}
          className={cn(
            'relative cursor-pointer rounded-xl border border-border bg-surface-alt overflow-hidden transition-shadow',
            focusedIndex !== null && focusedIndex !== i && 'opacity-80'
          )}
          onMouseEnter={() => setFocusedIndex(i)}
          animate={{
            scale: focusedIndex === i ? 1.02 : 1,
            zIndex: focusedIndex === i ? 10 : 1,
          }}
          transition={{ duration: 0.2 }}
        >
          {card.image && (
            <div className="relative h-32 w-full bg-surface">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={card.image}
                alt=""
                className="h-full w-full object-cover object-center"
              />
            </div>
          )}
          <div className="p-5">
            <h3 className="font-semibold text-text">{card.title}</h3>
            <p className="mt-2 text-muted text-sm leading-relaxed">{card.description}</p>
          </div>
          {focusedIndex === i && (
            <motion.div
              className="absolute inset-0 rounded-xl border-2 border-accent shadow-glow"
              layoutId="focus-ring"
              initial={false}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            />
          )}
        </motion.div>
      ))}
    </div>
  );
}
