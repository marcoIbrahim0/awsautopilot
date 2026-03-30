'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { ChevronDown, Globe, Menu, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/DropdownMenu';
import { getMarketingPrimaryLinks } from '@/components/landing/marketingLinks';
import { useLanguage } from '@/lib/i18n';
import { Language } from '@/locales/translations';

const LOCALES: { code: Language; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'de', label: 'Deutsch' },
  { code: 'fr', label: 'Français' },
];

const CALENDLY_URL = 'https://calendly.com/maromaher54/30min';

const NM_FLOAT = '8px 8px 20px #BBCBDD, -8px -8px 20px #FFFFFF';
const NM_FLOAT_HOVER = '10px 10px 28px #BBCBDD, -10px -10px 28px #FFFFFF';

export function SiteNav() {
  const [mounted, setMounted] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { language, setLanguage, t } = useLanguage();
  const navLinks = getMarketingPrimaryLinks(t);

  useEffect(() => {
    queueMicrotask(() => setMounted(true));

    const handleScroll = () => {
      // 800px roughly aligns with the bottom of the dark hero section SVG wave
      setScrolled(window.scrollY > 800);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    // Check initial scroll
    handleScroll();

    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <header className="fixed left-0 right-0 top-0 z-50 w-full pointer-events-none" style={{ background: 'transparent' }}>
      <div className="mx-auto max-w-7xl px-6 pt-5 flex items-center justify-between pointer-events-none relative">

        {/* Floating pill navbar - Now containing Logo */}
        <div className="flex flex-1 justify-center relative">
          <nav
            className={`pointer-events-auto flex h-14 items-center gap-1 rounded-full px-1.5 transition-all duration-500 ${scrolled ? 'bg-[#DDE6F0]' : 'bg-[#DDE6F0]/90 backdrop-blur-md'
              }`}
            style={{
              boxShadow: scrolled ? NM_FLOAT : '0 4px 30px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.4)',
            }}
          >
            {/* Logo inside pill */}
            <Link href="/" className="flex items-center shrink-0 pl-4 py-2 pr-2 mr-1">
              <Image
                src="/logo/ocypheris-logo.svg"
                alt={t('nav.logoAlt')}
                width={110}
                height={28}
                className="h-6 w-auto"
                priority
              />
            </Link>

            {/* Divider */}
            <div className="hidden md:block h-6 w-[1px] bg-[#BBCBDD] mx-2" />

            {/* Desktop nav links */}
            <div className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="px-4 py-2 rounded-full text-sm font-medium transition-all duration-200"
                  style={{
                    color: '#6B778C',
                    fontFamily: "'Inter', sans-serif",
                  }}
                  onMouseEnter={(e) => {
                    const el = e.currentTarget as HTMLElement;
                    el.style.color = '#2D3440';
                    el.style.boxShadow = 'inset 2px 2px 5px #BBCBDD, inset -2px -2px 5px #FFFFFF';
                  }}
                  onMouseLeave={(e) => {
                    const el = e.currentTarget as HTMLElement;
                    el.style.color = '#6B778C';
                    el.style.boxShadow = 'none';
                  }}
                >
                  {link.label}
                </Link>
              ))}
            </div>

            {/* Right side - inside pill */}
            <div className="flex items-center gap-1">
              {/* Language picker — desktop */}
              <div className="hidden md:flex items-center">
                {mounted ? (
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      className="flex items-center gap-1 rounded-full px-3 py-2 text-sm border-0 ring-0 outline-none transition-colors duration-200"
                      style={{ color: '#6B778C', fontFamily: "'Inter', sans-serif" }}
                    >
                      <Globe className="h-4 w-4" aria-hidden />
                      <span className="uppercase text-xs">{language}</span>
                      <ChevronDown className="h-3 w-3 opacity-50" aria-hidden />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent
                      align="end"
                      className="border-0 ring-0 outline-none mt-2"
                      style={{ background: '#DDE6F0', boxShadow: scrolled ? NM_FLOAT : '0 10px 40px rgba(0,0,0,0.3)', borderRadius: '1rem' }}
                    >
                      {LOCALES.map(({ code, label }) => (
                        <DropdownMenuItem
                          key={code}
                          onSelect={() => setLanguage(code)}
                          className="border-0 outline-none ring-0 focus:ring-0 cursor-pointer"
                          style={{ color: '#2D3440', fontFamily: "'Inter', sans-serif" }}
                        >
                          {label}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                ) : (
                  <div className="flex items-center gap-1 px-3 py-2" style={{ color: '#6B778C' }} aria-hidden>
                    <Globe className="h-4 w-4" />
                    <span className="text-xs uppercase">{language}</span>
                    <ChevronDown className="h-3 w-3 opacity-50" />
                  </div>
                )}
              </div>

              {/* CTA pill */}
              <Link
                href={CALENDLY_URL}
                target="_blank"
                rel="noreferrer"
                className="hidden md:flex items-center gap-2 px-6 h-10 rounded-full text-sm font-semibold transition-all duration-300 select-none ml-2"
                style={{
                  color: '#FFFFFF',
                  background: 'linear-gradient(135deg, #4A90E2 0%, #2b68c0 100%)',
                  boxShadow: '4px 4px 12px rgba(74,144,226,0.35)',
                  fontFamily: "'Space Grotesk', sans-serif",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.boxShadow = '6px 6px 18px rgba(74,144,226,0.45)';
                  (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)';
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.boxShadow = '4px 4px 12px rgba(74,144,226,0.35)';
                  (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
                }}
              >
                {t('nav.bookCall')}
              </Link>

              {/* Mobile hamburger */}
              <button
                type="button"
                className="inline-flex h-9 w-9 items-center justify-center rounded-full md:hidden transition-all duration-200"
                style={{ color: '#6B778C' }}
                onClick={() => setMobileOpen((open) => !open)}
                aria-expanded={mobileOpen}
                aria-label="Open navigation menu"
              >
                <AnimatePresence mode="wait" initial={false}>
                  <motion.span
                    key={mobileOpen ? 'close' : 'menu'}
                    initial={{ opacity: 0, rotate: -10, scale: 0.9 }}
                    animate={{ opacity: 1, rotate: 0, scale: 1 }}
                    exit={{ opacity: 0, rotate: 10, scale: 0.9 }}
                    transition={{ duration: 0.16, ease: 'easeOut' }}
                    className="inline-flex"
                  >
                    {mobileOpen ? <X className="h-4 w-4" aria-hidden /> : <Menu className="h-4 w-4" aria-hidden />}
                  </motion.span>
                </AnimatePresence>
              </button>
            </div>
          </nav>
        </div>

        {/* Mobile menu — Absolute positioned below the relative container */}
        <div className="absolute top-[calc(100%+0.5rem)] left-6 right-6 z-[60]">
          <AnimatePresence initial={false}>
            {mobileOpen ? (
              <motion.div
                initial={{ height: 0, opacity: 0, y: -8 }}
                animate={{ height: 'auto', opacity: 1, y: 0 }}
                exit={{ height: 0, opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                className="overflow-hidden pointer-events-auto rounded-3xl"
                style={{ background: '#DDE6F0', boxShadow: scrolled ? NM_FLOAT_HOVER : '0 15px 50px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255, 255, 255, 0.2)' }}
              >
                <nav className="flex flex-col gap-1 px-5 py-4">
                  {navLinks.map((link) => (
                    <Link
                      key={link.href}
                      href={link.href}
                      className="rounded-xl px-4 py-3 text-sm font-medium transition-colors"
                      style={{ color: '#6B778C', fontFamily: "'Inter', sans-serif" }}
                      onClick={() => setMobileOpen(false)}
                    >
                      {link.label}
                    </Link>
                  ))}
                  <Link
                    href={CALENDLY_URL}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() => setMobileOpen(false)}
                    className="mt-2 flex items-center justify-center rounded-full px-6 py-3 text-sm font-semibold transition-all duration-200"
                    style={{
                      color: '#FFFFFF',
                      background: 'linear-gradient(135deg, #4A90E2 0%, #2b68c0 100%)',
                      fontFamily: "'Space Grotesk', sans-serif",
                    }}
                  >
                    {t('nav.bookCall')}
                  </Link>
                </nav>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}
