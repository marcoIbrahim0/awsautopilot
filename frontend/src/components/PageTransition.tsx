'use client';

import { usePathname } from 'next/navigation';
import { motion } from 'motion/react';

/**
 * Wraps page content and applies a smooth fade when the route changes (redirect/navigation).
 */
export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <motion.div
      key={pathname}
      initial={false}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className="min-h-full"
    >
      {children}
    </motion.div>
  );
}
