'use client';

import Image from 'next/image';
import Link from 'next/link';
import { Linkedin } from 'lucide-react';
import { XIcon } from '@/components/ui/XIcon';
import { useLanguage } from '@/lib/i18n';
import { getMarketingFooterLinks, MARKETING_SOCIALS } from './marketingLinks';

type MarketingFooterProps = {
  compactWave?: boolean;
};

export function MarketingFooter({ compactWave = false }: MarketingFooterProps) {
  const { t } = useLanguage();
  const currentYear = new Date().getFullYear();
  const footerLinks = getMarketingFooterLinks(t);
  const gradientId = compactWave ? 'marketingFooterGlowCompact' : 'marketingFooterGlow';

  return (
    <>
      <div
        className={`relative w-full overflow-hidden bg-[#02040a] pointer-events-none z-20 ${compactWave ? 'h-24 sm:h-32' : 'h-32 sm:h-48'
          }`}
        aria-hidden="true"
        style={{ marginTop: '-2px' }}
      >
        <svg
          className="absolute top-0 left-0 w-full h-full scale-y-[1.05] origin-bottom"
          preserveAspectRatio="none"
          viewBox="0 0 1440 320"
        >
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#dde6f0" stopOpacity="1" />
              <stop offset="100%" stopColor="#02040a" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path fill="#dde6f0" d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z" />
          <path fill={`url(#${gradientId})`} opacity="0.6" transform="translate(0, 15) scale(1, 1.1)" d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z" />
          {!compactWave ? (
            <>
              <path fill={`url(#${gradientId})`} opacity="0.3" transform="translate(0, 30) scale(1, 1.25)" d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z" />
              <path fill={`url(#${gradientId})`} opacity="0.1" transform="translate(0, 50) scale(1, 1.4)" d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z" />
            </>
          ) : null}
        </svg>
      </div>

      <footer
        className="relative z-10 border-0 bg-transparent"
        style={{
          backgroundImage:
            "linear-gradient(180deg, rgba(2, 4, 10, 0.98) 0%, rgba(2, 4, 10, 0.0) 18%), linear-gradient(180deg, rgba(4, 9, 35, 0.0) 20%, rgba(10, 29, 76, 0.6) 58%, rgba(20, 41, 120, 0.95) 80%, rgba(31, 63, 188, 0.98) 100%), url('/images/footer-gradient.png')",
          backgroundSize: 'cover',
          backgroundPosition: 'center top',
          backgroundBlendMode: 'screen',
        }}
      >
        <div className="mx-auto max-w-6xl px-6 pt-20 pb-14 sm:pt-24 sm:pb-20">
          <div className="flex flex-col items-center text-center">
            <Image
              src="/logo/ocypheris-logo.svg"
              alt="Ocypheris"
              width={220}
              height={60}
              className="h-12 w-auto"
              loading="lazy"
            />

            <div className="mt-6 max-w-3xl text-center">
              <h3 className="text-lg font-semibold text-white">{t('footer.about.title')}</h3>
              <p className="mt-2 text-sm text-white/70 sm:text-base">
                {t('footer.about.desc')}
              </p>
            </div>

            <nav
              aria-label="Footer"
              className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-3 text-sm font-medium text-white/80"
            >
              {footerLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="transition hover:text-white"
                >
                  {link.label}
                </Link>
              ))}
            </nav>

            <div className="mt-8 flex items-center gap-4">
              {MARKETING_SOCIALS.map(({ label, href }) => {
                const Icon = label === 'LinkedIn' ? Linkedin : XIcon;

                return (
                  <Link
                    key={label}
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white/70 transition hover:border-white/40 hover:text-white"
                    aria-label={label}
                  >
                    <Icon className="h-5 w-5" aria-hidden />
                  </Link>
                );
              })}
            </div>

            <p className="mt-8 text-xs text-white/80">
              © {currentYear} {t('footer.copyright')}
            </p>
          </div>
        </div>
      </footer>
    </>
  );
}
