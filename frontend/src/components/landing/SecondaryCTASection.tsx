'use client';

import Link from 'next/link';
import { motion } from 'motion/react';
import { cn } from '@/lib/utils';

export function SecondaryCTASection() {
  return (
    <section
      className={cn(
        'relative overflow-hidden px-4 py-20 sm:px-6',
        'bg-gradient-to-b from-bg via-surface-alt/30 to-bg',
        'before:absolute before:inset-0 before:opacity-30',
        'before:bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(10,113,255,0.15),transparent)]'
      )}
    >
      <div className="relative z-10 mx-auto max-w-3xl text-center">
        <motion.h2
          className="text-2xl font-bold tracking-tight text-text sm:text-3xl"
          initial={{ opacity: 0, y: 8 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4 }}
        >
          Ready to see your baseline?
        </motion.h2>
        <motion.p
          className="mt-3 text-muted"
          initial={{ opacity: 0, y: 8 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4, delay: 0.05 }}
        >
          Connect read-only now and get your report within 48 hours.
        </motion.p>
        <motion.div
          className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row"
          initial={{ opacity: 0, y: 8 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <Link
            href="/signup"
            className="inline-flex items-center justify-center rounded-xl bg-[var(--primary-btn-bg)] px-5 py-2.5 text-base font-medium text-white transition-colors hover:bg-[var(--primary-btn-hover)] focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-dropdown-bg"
          >
            Get my baseline report
          </Link>
          {/* <Link
            href="#how-it-works"
            className="text-accent hover:underline text-sm font-medium"
          >
            See how it works
          </Link> */}
        </motion.div>
      </div>
    </section>
  );
}
