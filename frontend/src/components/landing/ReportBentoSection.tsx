'use client';

import { motion } from 'motion/react';
import { CometCard } from './CometCard';
import { cn } from '@/lib/utils';

const BENTO_TILES = [
  {
    title: 'Executive summary',
    description: 'Totals, severity breakdown, and the fastest path to reduce risk.',
    className: 'sm:col-span-2',
    image: undefined as string | undefined,
  },
  {
    title: 'Top risks (prioritized)',
    description: 'The few issues most likely to cause real incidents or audit pain.',
    className: '',
    image: undefined,
  },
  {
    title: 'Recommendations (5–10 next steps)',
    description: 'Concrete actions your team can ship this week.',
    className: '',
    image: undefined,
  },
];

export function ReportBentoSection() {
  return (
    <section className="relative px-4 py-20 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="text-center">
          <h2 className="text-3xl font-bold tracking-tight text-text sm:text-4xl">
            What you get in 48 hours
          </h2>
          <p className="mt-3 text-muted text-lg">
            A one-off baseline report—clear priorities, not dashboards.
          </p>
        </div>

        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {BENTO_TILES.map((tile, i) => (
            <motion.div
              key={tile.title}
              className={cn(tile.className)}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.3, delay: i * 0.05 }}
            >
              <CometCard image={tile.image}>
                <h3 className="font-semibold text-text">{tile.title}</h3>
                <p className="mt-2 text-muted text-sm leading-relaxed">{tile.description}</p>
              </CometCard>
            </motion.div>
          ))}
        </div>

        <p className="mt-6 text-center text-muted text-xs">
          One-off report. No WriteRole required.
        </p>
      </div>
    </section>
  );
}
