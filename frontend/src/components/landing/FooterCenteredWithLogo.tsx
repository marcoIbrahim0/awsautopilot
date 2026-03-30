'use client';

import Link from 'next/link';
import Image from 'next/image';
import { cn } from '@/lib/utils';

const FOOTER_LINKS = [
  { href: '/login', label: 'Login' },
  { href: '/privacy', label: 'Privacy' },
  { href: '/terms', label: 'Terms' },
];

interface FooterCenteredWithLogoProps {
  logoSrc?: string;
  logoAlt?: string;
  productName?: string;
  className?: string;
}

export function FooterCenteredWithLogo({
  logoSrc = '/logo/logo-light.svg',
  logoAlt = 'AWS Security Autopilot',
  productName = 'AWS Security Autopilot',
  className,
}: FooterCenteredWithLogoProps) {
  return (
    <footer className={cn('border-t border-border bg-bg', className)}>
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="flex flex-col items-center gap-8 text-center">
          <Link href="/landing" className="flex flex-col items-center gap-3 no-underline">
            {logoSrc ? (
              <span className="relative block h-10 w-10 sm:h-12 sm:w-12">
                <Image
                  src={logoSrc}
                  alt={logoAlt}
                  fill
                  className="object-contain"
                  priority
                />
              </span>
            ) : (
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/20 sm:h-12 sm:w-12">
                <svg
                  className="h-5 w-5 text-accent sm:h-6 sm:w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
                  />
                </svg>
              </span>
            )}
            <span className="font-semibold text-text">{productName}</span>
          </Link>
          <nav className="flex flex-wrap items-center justify-center gap-6">
            {FOOTER_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-muted hover:text-text text-sm font-medium transition-colors"
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <p className="text-muted text-xs max-w-md">
            Read-only baseline. No long-lived keys.
          </p>
        </div>
      </div>
    </footer>
  );
}
