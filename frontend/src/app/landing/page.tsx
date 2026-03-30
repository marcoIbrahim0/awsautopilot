'use client';

import Link from 'next/link';
import Image from 'next/image';
import {
  FileCheck,
  Shield,
  Wrench,
  Zap,
} from 'lucide-react';
import { SiteNav } from '@/components/site-nav';
import { AuroraBackground } from '@/components/ui/aurora-background';
import { CometCard } from '@/components/ui/comet-card';
import { BackgroundImageTexture } from '@/components/ui/bg-image-texture';
import { GlobalScrollTimeline } from '@/components/landing/GlobalScrollTimeline';
import { FlipWords } from '@/components/ui/flip-words';
import dynamic from 'next/dynamic';
// import { ContactPopoverForm } from '@/components/landing/ContactPopoverForm';
import { PrimaryCTANeumorphic } from '@/components/ui/PrimaryCTANeumorphic';
import { MarketingFooter } from '@/components/landing/MarketingFooter';
import { motion } from 'motion/react';

const MaximizeSecurityGrid = dynamic(() => import('@/components/landing/MaximizeSecurityGrid').then(mod => mod.MaximizeSecurityGrid), { ssr: true });
const SectionAnimator = dynamic(() => import('@/components/landing/SectionAnimator').then(mod => mod.SectionAnimator), { ssr: false });
const DeepSurfaceTrack = dynamic(() => import('@/components/landing/DeepSurfaceTrack').then(mod => mod.DeepSurfaceTrack), { ssr: false });
import { BaselineReportHighlight } from '@/components/landing/BaselineReportHighlight';

const BentoIntroGridSkeleton = () => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-10 w-full max-w-7xl mx-auto mt-16 px-6">
    {Array.from({ length: 3 }).map((_, index) => (
      <div
        key={index}
        className={`relative min-h-[340px] overflow-hidden rounded-[3rem] border border-white/40 bg-[var(--nm-base)] p-10 ${index === 0 ? 'md:col-span-2 lg:col-span-1' : ''
          }`}
        style={{
          boxShadow: '4px 4px 24px var(--nm-shadow-dark), -4px -4px 24px var(--nm-shadow-light)',
        }}
      >
        <div className={`relative z-10 ${index === 2 ? 'w-[65%]' : 'w-[60%]'}`}>
          <div className="mb-8 h-14 w-14 rounded-full nm-icon-well" />
          <div className="mb-4 h-7 w-3/4 rounded-full bg-[var(--nm-shadow-light)] opacity-70" />
          <div className="h-20 rounded-[1.75rem] bg-[var(--nm-shadow-light)] opacity-45" />
        </div>
      </div>
    ))}
  </div>
);

const BentoIntroGrid = dynamic(
  () => import('@/components/landing/BentoIntroGrid').then(mod => mod.BentoIntroGrid),
  {
    ssr: false,
    loading: () => <BentoIntroGridSkeleton />,
  }
);

// Must use the t() function inside the component for translation instead of constants outside
const PRIMARY_CTA_URL = 'https://calendly.com/maromaher54/30min';
// Moved SECURITY_POINTS inside component


import { useLanguage } from '@/lib/i18n';

export default function LandingPage() {
  const { t } = useLanguage();

  const SECURITY_POINTS = [
    { title: t('security.cards.access.title'), detail: t('security.cards.access.desc') },
    { title: t('security.cards.credentials.title'), detail: t('security.cards.credentials.desc') },
    { title: t('security.cards.isolation.title'), detail: t('security.cards.isolation.desc') },
    { title: t('security.cards.residency.title'), detail: t('security.cards.residency.desc'), needsVerification: true },
    { title: t('security.cards.encryption.title'), detail: t('security.cards.encryption.desc'), needsVerification: true },
  ];

  return (
    <>
      <SiteNav />
      <main className="min-h-screen bg-[var(--bg)]">
        <div className="dark bg-[var(--bg)]">
          <AuroraBackground className="min-h-[90.75vh]" showRadialGradient dark>
            <div
              className="relative z-10 mx-auto flex min-h-[90.75vh] max-w-5xl flex-col items-center justify-center px-6 py-12 sm:py-24 text-center"
            >
              <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
              >
                <Image
                  src="/logo/ocypheris-logo.svg"
                  alt="Ocypheris"
                  width={346}
                  height={95}
                  className="mb-8 h-[7rem] w-auto text-white"
                  priority
                />
              </motion.div>
              <motion.h1
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
                className="mb-2 text-4xl font-bold tracking-tight text-white sm:text-6xl md:text-[4.875rem]"
              >
                <FlipWords
                  words={[t('hero.title')]}
                  duration={4500}
                  startDelay={500}
                  className="px-0 text-white"
                />
              </motion.h1>
              <motion.div
                initial={{ opacity: 0, y: 22 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.16, ease: [0.16, 1, 0.3, 1] }}
                className="mx-auto mt-6 max-w-2xl text-xl sm:text-[1.65rem] leading-snug text-white/90"
              >
                <p>{t('hero.subtitle1')}</p>
                <p className="mt-3">
                  {t('hero.subtitle2')}
                </p>
              </motion.div>
              <motion.div
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.62, delay: 0.24, ease: [0.16, 1, 0.3, 1] }}
                className="mt-10 flex flex-wrap items-center justify-center gap-4"
              >
                <div className="hero-dark-neumorphic">
                  <PrimaryCTANeumorphic href={PRIMARY_CTA_URL} text={t('hero.cta')} className="nm-raised-lg" />
                </div>
                {/* <Link
                  href="#autopilot-explained"
                  className="inline-flex items-center justify-center rounded-lg border border-[var(--border)] bg-transparent px-8 py-3.5 text-[0.95rem] font-semibold text-white transition-all duration-300 hover:border-[var(--accent)] hover:bg-[rgba(10,113,255,0.05)] focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--accent)] nm-raised"
                >
                  See how it works
                </Link> */}
              </motion.div>
            </div>
          </AuroraBackground>
        </div>

        {/* Professional Glowing Edge SVG Wave Transition → Clay surface */}
        <div className="relative w-full h-32 sm:h-48 overflow-hidden pointer-events-none -mt-1 z-10" style={{ background: '#DDE6F0' }} aria-hidden="true">
          <svg
            className="absolute top-0 left-0 w-full h-full scale-y-[1.05] origin-top"
            preserveAspectRatio="none"
            viewBox="0 0 1440 320"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="glowGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#040817" stopOpacity="1" />
                <stop offset="100%" stopColor="#DDE6F0" stopOpacity="0" />
              </linearGradient>
            </defs>
            {/* Base Dark Wave */}
            <path
              fill="#040817"
              fillOpacity="1"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
            {/* Layer 1: Soft edge blur */}
            <path
              fill="url(#glowGradient)"
              opacity="0.6"
              transform="translate(0, 15) scale(1, 1.1)"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
            {/* Layer 2: Softer, wider edge blur */}
            <path
              fill="url(#glowGradient)"
              opacity="0.3"
              transform="translate(0, 30) scale(1, 1.25)"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
            {/* Layer 3: Widest diffusion glow */}
            <path
              fill="url(#glowGradient)"
              opacity="0.1"
              transform="translate(0, 50) scale(1, 1.4)"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
          </svg>
        </div>

        {/* Start Light Neumorphic Section */}
        <div className="landing-neumorphic">

          <GlobalScrollTimeline>
            {/* B. Autopilot, Explained (MOVED UP) */}
            <section
              id="autopilot-explained"
              className="relative z-10 border-0 bg-transparent px-6 pt-8 pb-12 sm:pt-12 sm:pb-16"
              aria-labelledby="autopilot-explained-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-[85rem]">
                <div className="inline-block max-w-fit mb-4">
                  <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)]" aria-hidden />
                  <p className="font-mono text-sm uppercase tracking-[0.2em] text-[var(--accent)] mb-3">
                    {t('autopilot.label')}
                  </p>
                  <h2 id="autopilot-explained-title" className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl max-w-3xl" style={{ color: 'var(--nm-text)' }}>
                    {t('autopilot.title')}<span className="nm-text-accent">{t('autopilot.titleHighlight')}</span>
                  </h2>
                  <p className="mt-4 text-lg max-w-2xl leading-relaxed" style={{ color: 'var(--nm-text-muted)' }}>
                    {t('autopilot.desc')}
                  </p>
                </div>

                <BentoIntroGrid />
              </div>
            </section>

            {/* Integrations Marquee removed */}

            {/* Maximize Security Sticky Scroll */}
            <section
              id="proof"
              className="relative z-10 border-0 bg-transparent px-6 pt-16 pb-0 sm:pt-24 sm:pb-0"
              aria-labelledby="proof-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-[85rem]">
                <div className="flex flex-col items-start justify-between gap-6 md:flex-row md:items-end md:gap-4">
                  <div className="inline-block max-w-fit">
                    <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)]" aria-hidden />
                    <h2 id="proof-title" className="text-3xl font-bold tracking-tight sm:text-4xl" style={{ color: 'var(--nm-text)' }}>
                      {t('proof.title')}<span className="nm-text-accent">{t('proof.titleHighlight')}</span>
                    </h2>
                    <p className="mt-3 max-w-3xl text-lg sm:text-xl" style={{ color: 'var(--nm-text-muted)' }}>
                      {t('proof.desc')}
                    </p>
                  </div>
                  <div className="shrink-0 mb-[2px]">
                    {/* <Link
                      href="#how-it-works"
                      className="nm-btn-secondary"
                      style={{ fontSize: '0.875rem', padding: '0.625rem 1.5rem' }}
                    >
                      See how it works
                    </Link> */}
                  </div>
                </div>

                <div className="lg:-mt-28 xl:-mt-32">
                  <MaximizeSecurityGrid />
                </div>
              </div>
            </section>


            <section
              id="security-data"
              className="relative z-10 px-6 py-24 overflow-hidden"
              aria-labelledby="security-data-title"
              data-landing-animate
            >
              <div className="absolute top-0 left-0 w-full h-full pointer-events-none z-0">
                <div className="nm-raised absolute -top-20 -left-20 w-96 h-96 opacity-40 animate-[float_6s_ease-in-out_infinite] rounded-full" style={{ background: 'var(--nm-base)' }}></div>
                <div className="nm-raised absolute bottom-20 -right-20 w-64 h-64 opacity-30 rounded-full" style={{ background: 'var(--nm-base)', animation: 'float 6s ease-in-out infinite', animationDelay: '2s' }}></div>
                <svg className="absolute top-0 left-0 w-full h-full opacity-10" fill="none" viewBox="0 0 1440 800" xmlns="http://www.w3.org/2000/svg">
                  <path d="M-100 200 C 300 100, 700 600, 1500 400" fill="transparent" stroke="var(--accent)" strokeWidth="2"></path>
                </svg>
              </div>

              <div className="max-w-7xl mx-auto relative z-10">
                <div className="text-center mb-24">
                  <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)] mx-auto" aria-hidden />
                  <span className="font-semibold tracking-widest uppercase text-sm mb-4 block" style={{ color: 'var(--accent)' }}>{t('security.label')}</span>
                  <h2 id="security-data-title" className="text-4xl md:text-5xl font-bold mb-6" style={{ color: 'var(--nm-text)' }}>{t('security.title')}</h2>
                  <p className="text-lg max-w-2xl mx-auto" style={{ color: 'var(--nm-text-muted)' }}>
                    {t('security.desc')}
                  </p>
                </div>

                <div className="relative flex flex-col space-y-32">
                  {/* 01: Access Model */}
                  <div className="flex flex-col md:flex-row items-center gap-12 group">
                    <div className="w-full md:w-1/2 flex justify-center md:justify-end order-2 md:order-1">
                      <div className="nm-raised-lg p-12 rounded-full w-64 h-64 flex flex-col items-center justify-center text-center transition-all duration-300 hover:-translate-y-1 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                        <svg className="w-12 h-12 mb-4" style={{ color: 'var(--accent)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"></path></svg>
                        <span className="text-xs font-bold uppercase tracking-tighter" style={{ color: 'var(--accent)' }}>Verified</span>
                      </div>
                    </div>
                    <div className="w-full md:w-1/2 order-1 md:order-2">
                      <h3 className="text-3xl font-bold mb-4" style={{ color: 'var(--nm-text)' }}>{t('security.cards.access.title')}</h3>
                      <p className="leading-relaxed max-w-md" style={{ color: 'var(--nm-text-muted)' }} dangerouslySetInnerHTML={{ __html: t('security.cards.access.desc').replace('STS:AssumeRole', '<span class="font-medium" style="color: var(--accent)">STS:AssumeRole</span>') }} />
                    </div>
                  </div>

                  {/* 02: Credentials Handling */}
                  <div className="flex flex-col md:flex-row items-center gap-12 group">
                    <div className="w-full md:w-1/2 text-left md:text-right">
                      <h3 className="text-3xl font-bold mb-4" style={{ color: 'var(--nm-text)' }}>{t('security.cards.credentials.title')}</h3>
                      <p className="leading-relaxed max-w-md md:ml-auto" style={{ color: 'var(--nm-text-muted)' }}>
                        {t('security.cards.credentials.desc')}
                      </p>
                    </div>
                    <div className="w-full md:w-1/2 flex justify-center md:justify-start">
                      <div className="nm-raised-lg p-12 rounded-[3rem] w-72 h-48 flex flex-col items-center justify-center rotate-3 group-hover:rotate-0 transition-all duration-300 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                        <svg className="w-12 h-12 mb-2" style={{ color: 'var(--accent)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"></path></svg>
                        <div className="h-[2px] w-24 mb-2 bg-gradient-to-r from-transparent via-[var(--accent)] to-transparent opacity-50"></div>
                        <span className="text-sm font-medium" style={{ color: 'var(--nm-text)' }}>Zero Storage Policy</span>
                      </div>
                    </div>
                  </div>

                  {/* 03: Tenant Isolation */}
                  <div className="flex flex-col md:flex-row items-center gap-12 group">
                    <div className="w-full md:w-1/2 flex justify-center md:justify-end order-2 md:order-1">
                      <div className="nm-raised-lg p-12 rounded-3xl w-64 h-64 flex flex-col items-center justify-center text-center -rotate-6 group-hover:rotate-0 transition-all duration-300 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                        <div className="relative">
                          <div className="w-16 h-16 rounded-xl nm-inset mb-4 flex items-center justify-center" style={{ background: 'var(--nm-base)' }}>
                            <div className="w-8 h-8 rounded shrink-0 nm-raised" style={{ background: 'var(--accent)', opacity: 0.8 }} />
                          </div>
                          <div className="absolute -top-2 -right-2 w-16 h-16 border-2 rounded-xl opacity-20 pointer-events-none" style={{ borderColor: 'var(--accent)' }}></div>
                        </div>
                        <span className="text-sm font-bold mt-2 hover:opacity-80" style={{ color: 'var(--accent)' }}>Encapsulated</span>
                      </div>
                    </div>
                    <div className="w-full md:w-1/2 order-1 md:order-2">
                      <h3 className="text-3xl font-bold mb-4" style={{ color: 'var(--nm-text)' }}>{t('security.cards.isolation.title')}</h3>
                      <p className="leading-relaxed max-w-md" style={{ color: 'var(--nm-text-muted)' }} dangerouslySetInnerHTML={{ __html: t('security.cards.isolation.desc').replace('tenant_id', '<span class="italic font-medium" style="color: var(--accent)">tenant_id</span>') }} />
                    </div>
                  </div>

                  {/* 04: Data Residency & Encryption */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-12 mt-12">
                    <div className="nm-raised p-10 rounded-[4rem] group transition-all duration-300 hover:-translate-y-1 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                      <div className="flex items-start gap-6">
                        <div className="p-4 rounded-2xl nm-inset shrink-0" style={{ background: 'var(--nm-base)' }}>
                          <svg className="w-8 h-8" style={{ color: 'var(--accent)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 002 2h1.5a2.5 2.5 0 012.5 2.5V17m-6 5v-1.5a2.5 2.5 0 012.5-2.5h2.5a2.5 2.5 0 012.5 2.5V22M12 22a10 10 0 100-20 10 10 0 000 20z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"></path></svg>
                        </div>
                        <div>
                          <h4 className="text-2xl font-bold mb-2" style={{ color: 'var(--nm-text)' }}>{t('security.cards.residency.title')}</h4>
                          <p style={{ color: 'var(--nm-text-muted)' }}>
                            {t('security.cards.residency.desc')}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="nm-raised p-10 rounded-[4rem] group transition-all duration-300 hover:-translate-y-1 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                      <div className="flex items-start gap-6">
                        <div className="p-4 rounded-2xl nm-inset shrink-0" style={{ background: 'var(--nm-base)' }}>
                          <svg className="w-8 h-8" style={{ color: 'var(--accent)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04M12 21.75c-2.676 0-5.216-.584-7.499-1.632A12.005 12.005 0 013 12c0-5.335 3.468-9.859 8.25-11.417a12.005 12.005 0 019.75 0C20.532 2.141 24 6.665 24 12c0 3.321-1.343 6.328-3.501 8.518A12.005 12.005 0 0112 21.75z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"></path></svg>
                        </div>
                        <div>
                          <h4 className="text-2xl font-bold mb-2" style={{ color: 'var(--nm-text)' }}>{t('security.cards.encryption.title')}</h4>
                          <p style={{ color: 'var(--nm-text-muted)' }}>
                            {t('security.cards.encryption.desc')}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-24 flex justify-center w-full">
                  <Link href="/security" className="nm-btn-secondary" style={{ padding: '1rem 2rem', fontSize: '1rem' }}>
                    {t('security.cta')} <span className="ml-2 font-mono">→</span>
                  </Link>
                </div>
              </div>
            </section>

            <BaselineReportHighlight />

            <DeepSurfaceTrack />

            <section
              id="faq"
              className="relative z-10 border-0 bg-transparent px-6 py-16 sm:py-24"
              aria-labelledby="faq-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-6xl">
                <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)]" aria-hidden />
                <div className="grid gap-10 lg:grid-cols-[1.1fr_1.4fr] lg:items-start">
                  <div>
                    <h2 id="faq-title" className="text-3xl font-bold tracking-tight sm:text-4xl" style={{ color: 'var(--nm-text)' }}>
                      {t('faq.title')}
                    </h2>
                    <p className="mt-4 text-lg" style={{ color: 'var(--nm-text-muted)' }}>
                      {t('faq.desc')}
                    </p>
                    <div className="mt-8">
                      <Link href="/faq" className="nm-btn-secondary" style={{ padding: '0.875rem 2rem', fontSize: '1rem' }}>
                        {t('faq.cta')}
                      </Link>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section
              id="team"
              className="relative z-10 border-0 bg-transparent px-6 py-16 sm:py-24"
              aria-labelledby="team-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-6xl">
                <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)]" aria-hidden />
                <h2 id="team-title" className="text-2xl font-semibold tracking-tight sm:text-3xl" style={{ color: 'var(--nm-text)' }}>
                  {t('team.title')}
                </h2>
                <div className="mt-6 flex items-start gap-4">
                  {/* TODO MKT-027: replace with real headshot before launch */}
                  {/* @ts-expect-error MKT-027 requires an alt attribute on this placeholder div */}
                  <div className="h-16 w-16 rounded-full nm-icon-well shrink-0 bg-gray-300" alt="Founder headshot" />
                  <p className="max-w-4xl text-base sm:text-lg" style={{ color: 'var(--nm-text-muted)' }}>
                    {t('team.desc')}
                  </p>
                </div>
              </div>
            </section>

            {/* Final CTA / Contact */}
            <section
              id="contact"
              className="relative z-10 border-0 bg-transparent px-6 py-16 sm:py-24"
              aria-labelledby="contact-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-6xl">
                <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-start">
                  <div>
                    <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)]" aria-hidden />
                    <h2 id="contact-title" className="text-3xl font-bold tracking-tight sm:text-4xl" style={{ color: 'var(--nm-text)' }}>
                      {t('contact.title')}
                    </h2>
                    <p className="mt-2 text-lg" style={{ color: 'var(--nm-text-muted)' }}>
                      {t('contact.desc1')}
                    </p>
                    <p className="mt-6" style={{ color: 'var(--nm-text-muted)' }}>
                      {t('contact.desc2')}
                      <br />
                      {t('contact.desc3')}
                    </p>
                    <div className="mt-8 flex flex-wrap items-center gap-4">
                      <PrimaryCTANeumorphic href={PRIMARY_CTA_URL} text={t('contact.cta1')} />
                      <Link
                        href={PRIMARY_CTA_URL}
                        target="_blank"
                        rel="noreferrer"
                        className="nm-btn-secondary"
                        style={{ padding: '0.625rem 1.5rem', fontSize: '0.875rem' }}
                      >
                        {t('contact.cta2')}
                      </Link>
                    </div>
                  </div>

                  <div className="space-y-6">
                    <div>
                      <h3 className="text-xl font-semibold" style={{ color: 'var(--nm-text)' }}>{t('contact.side.title')}</h3>
                      <p className="mt-2 text-base" style={{ color: 'var(--nm-text-muted)' }}>
                        {t('contact.side.desc1')}
                        <Link
                          href="mailto:sales@ocypheris.com"
                          className="font-semibold text-[var(--accent)] transition hover:text-[var(--nm-text)]"
                        >
                          sales@ocypheris.com
                        </Link>
                        .
                      </p>
                      <p className="mt-4 text-sm" style={{ color: 'var(--nm-text-muted)' }}>
                        {t('contact.side.desc2')}
                      </p>
                    </div>

                    {/* <ContactPopoverForm /> */}
                  </div>
                </div>
              </div>
            </section>
          </GlobalScrollTimeline>
        </div>

        <MarketingFooter />
        <SectionAnimator />
      </main>
    </>
  );
}
