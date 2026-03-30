'use client';

import { motion } from 'motion/react';
import Link from 'next/link';
import { Button } from '@/components/ui/Button';

/**
 * Aceternity-style auth form card (signup/signin).
 * Uses motion for entrance animation and shadow-input styling for inputs.
 * @see https://ui.aceternity.com/components/signup-form
 */

export interface AuthFormCardProps {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  submitLabel: string;
  submitLoading?: boolean;
  /** Shown when submitLoading is true; defaults to submitLabel + "..." */
  submitLoadingLabel?: string;
  onSubmit: (e: React.FormEvent) => void;
  error: string | null;
  footerLabel: string;
  footerHref: string;
  footerLinkLabel: string;
  /** Optional icon/brand above title (e.g. shield logo) */
  icon?: React.ReactNode;
}

export function AuthFormCard({
  title,
  subtitle,
  children,
  submitLabel,
  submitLoading = false,
  submitLoadingLabel,
  onSubmit,
  error,
  footerLabel,
  footerHref,
  footerLinkLabel,
  icon,
}: AuthFormCardProps) {
  return (
    <motion.div
      className="w-full max-w-md"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }}
    >
      {/* Brand / Icon */}
      <div className="text-center mb-8">
        {icon && (
          <div className="w-12 h-12 bg-accent/20 rounded-xl flex items-center justify-center mx-auto mb-4">
            {icon}
          </div>
        )}
        <h1 className="text-2xl font-bold text-text">{title}</h1>
        <p className="text-muted mt-2">{subtitle}</p>
      </div>

      {/* Card */}
      <motion.div
        className="bg-surface border border-border rounded-2xl p-6 sm:p-8"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.08 }}
      >
        <form onSubmit={onSubmit} className="space-y-5">
          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="p-3 bg-danger/10 border border-danger/20 rounded-xl"
            >
              <p className="text-sm text-danger">{error}</p>
            </motion.div>
          )}

          {children}

          <Button
            type="submit"
            variant="primary"
            className="w-full inline-flex items-center justify-center gap-2 py-3 rounded-xl font-medium"
            disabled={submitLoading}
            isLoading={submitLoading}
          >
            {submitLoading ? (
              submitLoadingLabel ?? `${submitLabel}...`
            ) : (
              <>
                {submitLabel}
                <span aria-hidden>→</span>
              </>
            )}
          </Button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-sm text-muted">
            {footerLabel}{' '}
            <Link
              href={footerHref}
              className="text-accent hover:text-accent-hover font-medium transition-colors"
            >
              {footerLinkLabel}
            </Link>
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}
