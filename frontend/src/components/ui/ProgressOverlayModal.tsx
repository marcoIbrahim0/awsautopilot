'use client';

import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'motion/react';
import { Button } from '@/components/ui/Button';

interface ProgressOverlayModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  progress: number;
  detail?: string | null;
  done?: boolean;
  onClose?: () => void;
}

const transition = { duration: 0.2, ease: 'easeOut' as const };

export function ProgressOverlayModal({
  isOpen,
  title,
  message,
  progress,
  detail,
  done = false,
  onClose,
}: ProgressOverlayModalProps) {
  useEffect(() => {
    if (!isOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [isOpen]);

  if (typeof window === 'undefined') return null;

  const boundedProgress = Math.max(0, Math.min(100, Math.round(progress)));

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
          <motion.div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={transition}
            aria-hidden
          />
          <motion.div
            className="relative w-full max-w-lg rounded-2xl border border-border bg-surface p-6 shadow-premium"
            role="dialog"
            aria-modal="true"
            aria-live="polite"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={transition}
          >
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-text">{title}</h2>
              <p className="mt-1 text-sm text-muted">{message}</p>
            </div>

            <div className="mb-2 h-2 w-full overflow-hidden rounded-full bg-bg">
              <motion.div
                className="h-full rounded-full bg-accent"
                animate={{ width: `${boundedProgress}%` }}
                transition={{ duration: 0.3, ease: 'easeOut' }}
              />
            </div>
            <p className="mb-4 text-xs text-muted">{boundedProgress}%</p>

            {detail ? <p className="mb-4 text-sm text-text">{detail}</p> : null}

            {done && onClose ? (
              <div className="flex justify-end">
                <Button variant="primary" size="sm" onClick={onClose}>
                  Done
                </Button>
              </div>
            ) : null}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}

