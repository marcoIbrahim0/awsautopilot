'use client';

import Link from 'next/link';
import { cn } from '@/lib/utils';

const FOOTER_LINKS = [
  { href: '/login', label: 'Login' },
  { href: '/legal/privacy', label: 'Privacy Policy' },
  { href: '/legal/terms', label: 'Terms of Service' },
  { href: '/legal/cookies', label: 'Cookie Policy' },
];

export function LandingFooter() {
  return (
    <footer className="border-t border-border bg-bg">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-4 py-8 sm:flex-row sm:px-6">
        <div className="flex flex-wrap items-center justify-center gap-6">
          {FOOTER_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-muted hover:text-text text-sm font-medium transition-colors"
            >
              {link.label}
            </Link>
          ))}
        </div>
        <p className="text-muted text-xs">
          Read-only baseline. No long-lived keys.
        </p>
      </div>
    </footer>
  );
}
