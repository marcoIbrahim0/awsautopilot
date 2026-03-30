'use client';

import Link from 'next/link';
import { SiteNav } from '@/components/site-nav';
import { Shield, Key, Database, Lock, CheckCircle, LayoutDashboard, Search, AlertTriangle } from 'lucide-react';
import { SectionAnimator } from '@/components/landing/SectionAnimator';
import { MarketingFooter } from '@/components/landing/MarketingFooter';

import { useLanguage } from '@/lib/i18n';

export default function SecurityWhitepaper() {
  const { t } = useLanguage();
  return (
    <>
      <SiteNav />
      <main className="landing-neumorphic min-h-screen font-sans">

        {/* Hero Section */}
        <section className="relative z-10 pt-32 pb-16 px-6 text-center">
          <div className="max-w-4xl mx-auto">
            <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)] mx-auto" aria-hidden />
            <span className="font-semibold tracking-widest uppercase text-sm mb-4 block" style={{ color: 'var(--accent)' }}>{t('securityPage.hero.label')}</span>
            <h1 className="text-4xl md:text-6xl font-bold mb-6 tracking-tight" style={{ color: 'var(--nm-text)' }}>
              {t('securityPage.hero.title')}
            </h1>
            <p className="text-xl max-w-2xl mx-auto leading-relaxed" style={{ color: 'var(--nm-text-muted)' }}>
              {t('securityPage.hero.desc')}
            </p>
          </div>
        </section>

        {/* Content */}
        <section className="relative z-10 border-0 bg-transparent px-6 py-12">
          <div className="max-w-5xl mx-auto space-y-16">

            {/* 1. Executive Summary */}
            <div className="nm-raised-lg p-8 sm:p-12" style={{ background: 'var(--nm-base)' }}>
              <div className="flex items-center gap-4 mb-6">
                <div className="p-3 rounded-full nm-inset" style={{ background: 'var(--nm-base)', color: 'var(--accent)' }}>
                  <LayoutDashboard className="w-6 h-6" />
                </div>
                <h2 className="text-2xl font-bold" style={{ color: 'var(--nm-text)' }}>{t('securityPage.exec.title')}</h2>
              </div>
              <p className="leading-relaxed" style={{ color: 'var(--nm-text-muted)' }}>
                {t('securityPage.exec.desc')}
              </p>
            </div>

            {/* Grid of core tenets */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* 2. Access Model */}
              <div className="nm-raised-lg p-8 group transition-all duration-300 hover:-translate-y-1 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                <div className="mb-6 h-12 w-12 rounded-full nm-icon-well flex items-center justify-center text-[var(--accent)]">
                  <Key className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold mb-3" style={{ color: 'var(--nm-text)' }}>{t('securityPage.cards.access.title')}</h3>
                <p className="leading-relaxed text-sm" style={{ color: 'var(--nm-text-muted)' }}>
                  {t('securityPage.cards.access.desc')}
                </p>
              </div>

              {/* 3. Zero Credential Storage */}
              <div className="nm-raised-lg p-8 group transition-all duration-300 hover:-translate-y-1 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                <div className="mb-6 h-12 w-12 rounded-full nm-icon-well flex items-center justify-center text-[var(--accent)]">
                  <Shield className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold mb-3" style={{ color: 'var(--nm-text)' }}>{t('securityPage.cards.zero.title')}</h3>
                <p className="leading-relaxed text-sm" style={{ color: 'var(--nm-text-muted)' }}>
                  {t('securityPage.cards.zero.desc')}
                </p>
              </div>

              {/* 4. Tenant Isolation */}
              <div className="nm-raised-lg p-8 group transition-all duration-300 hover:-translate-y-1 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                <div className="mb-6 h-12 w-12 rounded-full nm-icon-well flex items-center justify-center text-[var(--accent)]">
                  <Database className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold mb-3" style={{ color: 'var(--nm-text)' }}>{t('securityPage.cards.isolation.title')}</h3>
                <p className="leading-relaxed text-sm" style={{ color: 'var(--nm-text-muted)' }}>
                  {t('securityPage.cards.isolation.desc')}
                </p>
              </div>

              {/* 5. Data Encryption & Residency */}
              <div className="nm-raised-lg p-8 group transition-all duration-300 hover:-translate-y-1 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                <div className="mb-6 h-12 w-12 rounded-full nm-icon-well flex items-center justify-center text-[var(--accent)]">
                  <Lock className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold mb-3" style={{ color: 'var(--nm-text)' }}>{t('securityPage.cards.encryption.title')}</h3>
                <p className="leading-relaxed text-sm" style={{ color: 'var(--nm-text-muted)' }}>
                  {t('securityPage.cards.encryption.desc')}
                </p>
              </div>

              {/* 6. Remediation Safety Controls */}
              <div className="nm-raised-lg p-8 group transition-all duration-300 hover:-translate-y-1 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                <div className="mb-6 h-12 w-12 rounded-full nm-icon-well flex items-center justify-center text-[var(--accent)]">
                  <CheckCircle className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold mb-3" style={{ color: 'var(--nm-text)' }}>{t('securityPage.cards.controls.title')}</h3>
                <p className="leading-relaxed text-sm" style={{ color: 'var(--nm-text-muted)' }}>
                  {t('securityPage.cards.controls.desc')}
                </p>
              </div>

              {/* 7. Least Privilege IAM */}
              <div className="nm-raised-lg p-8 group transition-all duration-300 hover:-translate-y-1 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                <div className="mb-6 h-12 w-12 rounded-full nm-icon-well flex items-center justify-center text-[var(--accent)]">
                  <AlertTriangle className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold mb-3" style={{ color: 'var(--nm-text)' }}>{t('securityPage.cards.iam.title')}</h3>
                <p className="leading-relaxed text-sm" style={{ color: 'var(--nm-text-muted)' }}>
                  {t('securityPage.cards.iam.desc')}
                </p>
              </div>
            </div>

            {/* 8. Audit Trail & Evidence */}
            <div className="nm-raised-lg p-8 sm:p-12 border-t-4 border-[var(--accent)]" style={{ background: 'var(--nm-base)' }}>
              <div className="flex items-center gap-4 mb-6">
                <div className="p-3 rounded-full nm-inset" style={{ background: 'var(--nm-base)', color: 'var(--accent)' }}>
                  <Search className="w-6 h-6" />
                </div>
                <h2 className="text-2xl font-bold" style={{ color: 'var(--nm-text)' }}>{t('securityPage.audit.title')}</h2>
              </div>
              <div className="space-y-4" style={{ color: 'var(--nm-text-muted)' }}>
                <p className="leading-relaxed">
                  {t('securityPage.audit.desc1')}
                </p>
                <p className="leading-relaxed">
                  {t('securityPage.audit.desc2')}
                </p>
              </div>
            </div>

            <div className="text-center pt-8 pb-12">
              <Link href="/landing#security-data" className="inline-flex items-center justify-center px-8 py-4 rounded-full font-bold transition-all duration-300 nm-raised hover:nm-raised-xl active:nm-inset" style={{ color: 'var(--nm-text)', background: 'var(--nm-base)' }}>
                <span className="mr-2 font-mono">←</span> {t('securityPage.cta')}
              </Link>
            </div>

          </div>
        </section>

        <MarketingFooter compactWave />

        <SectionAnimator />
      </main>
    </>
  );
}
