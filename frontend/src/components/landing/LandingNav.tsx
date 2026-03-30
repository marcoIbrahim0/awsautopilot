'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { motion, AnimatePresence } from 'motion/react';
import { Menu, X } from 'lucide-react';
import { cn } from '@/lib/utils';

const LOGO_SRC = '/logo/logo-light.svg';
const CALENDLY_URL = 'https://calendly.com/maromaher54/30min';

const NAV_LINKS = [
  { href: '/login', label: 'Login' },
  { href: '/docs', label: 'Docs' },
];

export function LandingNav() {
  const [expanded, setExpanded] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-bg/95 backdrop-blur supports-[backdrop-filter]:bg-bg/80">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link
          href="/landing"
          className="flex min-w-0 items-center gap-2 font-semibold text-text no-underline"
        >
          <span className="relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-lg bg-accent/20">
            {LOGO_SRC ? (
              <Image src={LOGO_SRC} alt="AWS Security Autopilot" fill className="object-contain p-1" />
            ) : (
              <svg className="h-4 w-4 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            )}
          </span>
          <span className="truncate text-sm sm:hidden">Autopilot</span>
          <span className="hidden sm:inline">AWS Security Autopilot</span>
        </Link>

        <div className="flex items-center gap-2 sm:gap-4">
          <Link
            href={CALENDLY_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center rounded-xl bg-[var(--primary-btn-bg)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[var(--primary-btn-hover)] focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-dropdown-bg md:hidden"
          >
            Book a call
          </Link>
          <nav className="hidden items-center gap-4 md:flex">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-muted hover:text-text text-sm font-medium transition-colors"
              >
                {link.label}
              </Link>
            ))}
            <Link
              href="/signup"
              className="inline-flex items-center justify-center rounded-xl bg-[var(--primary-btn-bg)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[var(--primary-btn-hover)] focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-dropdown-bg"
            >
              Get my baseline report
            </Link>
          </nav>
          <button
            type="button"
            className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-bg text-muted transition-colors hover:bg-surface hover:text-text md:hidden"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            aria-label="Toggle menu"
          >
            {expanded ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-border bg-bg md:hidden"
          >
            <div className="flex flex-col gap-2 px-4 py-3">
              {NAV_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="text-muted hover:text-text py-2 text-sm font-medium"
                  onClick={() => setExpanded(false)}
                >
                  {link.label}
                </Link>
              ))}
              <Link
                href={CALENDLY_URL}
                target="_blank"
                rel="noreferrer"
                onClick={() => setExpanded(false)}
                className="mt-2 inline-flex items-center justify-center rounded-xl bg-[var(--primary-btn-bg)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--primary-btn-hover)] focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-dropdown-bg"
              >
                Book a call
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
