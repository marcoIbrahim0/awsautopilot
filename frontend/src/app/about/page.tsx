'use client';

import Link from 'next/link';
import { SiteNav } from '@/components/site-nav';
import { Shield, Zap, Target } from 'lucide-react';
import { SectionAnimator } from '@/components/landing/SectionAnimator';
import { MarketingFooter } from '@/components/landing/MarketingFooter';

import { useLanguage } from '@/lib/i18n';

export default function AboutPage() {
    const { t } = useLanguage();

    return (
        <>
            <SiteNav />
            <main className="landing-neumorphic min-h-screen font-sans">

                {/* Hero Section */}
                <section className="relative z-10 pt-32 pb-16 px-6 text-center">
                    <div className="max-w-4xl mx-auto">
                        <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)] mx-auto" aria-hidden />
                        <span className="font-semibold tracking-widest uppercase text-sm mb-4 block" style={{ color: 'var(--accent)' }}>{t('about.hero.label')}</span>
                        <h1 className="text-4xl md:text-6xl font-bold mb-6 tracking-tight" style={{ color: 'var(--nm-text)' }}>
                            {t('about.hero.title')}
                        </h1>
                        <p className="text-xl max-w-2xl mx-auto leading-relaxed" style={{ color: 'var(--nm-text-muted)' }}>
                            {t('about.hero.desc')}
                        </p>
                    </div>
                </section>

                {/* Content */}
                <section className="relative z-10 border-0 bg-transparent px-6 py-12">
                    <div className="max-w-5xl mx-auto space-y-16">

                        {/* Our Mission */}
                        <div className="nm-raised-lg p-8 sm:p-12" style={{ background: 'var(--nm-base)' }}>
                            <div className="flex items-center gap-4 mb-6">
                                <div className="p-3 rounded-full nm-inset" style={{ background: 'var(--nm-base)', color: 'var(--accent)' }}>
                                    <Target className="w-6 h-6" />
                                </div>
                                <h2 className="text-2xl font-bold" style={{ color: 'var(--nm-text)' }}>{t('about.mission.title')}</h2>
                            </div>
                            <p className="leading-relaxed mb-6 text-lg" style={{ color: 'var(--nm-text-muted)' }}>
                                {t('about.mission.desc1')}
                            </p>
                            <p className="leading-relaxed text-lg" style={{ color: 'var(--nm-text-muted)' }}>
                                {t('about.mission.desc2')}
                            </p>
                        </div>

                        {/* Grid of core tenets */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                            {/* Trust */}
                            <div className="nm-raised-lg p-8 group transition-all duration-300 hover:-translate-y-1 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                                <div className="mb-6 h-12 w-12 rounded-full nm-icon-well flex items-center justify-center text-[var(--accent)]">
                                    <Shield className="w-6 h-6" />
                                </div>
                                <h3 className="text-xl font-bold mb-3" style={{ color: 'var(--nm-text)' }}>{t('about.cards.safety.title')}</h3>
                                <p className="leading-relaxed text-sm" style={{ color: 'var(--nm-text-muted)' }}>
                                    {t('about.cards.safety.desc')}
                                </p>
                            </div>

                            {/* Action */}
                            <div className="nm-raised-lg p-8 group transition-all duration-300 hover:-translate-y-1 hover:nm-raised-xl" style={{ background: 'var(--nm-base)' }}>
                                <div className="mb-6 h-12 w-12 rounded-full nm-icon-well flex items-center justify-center text-[var(--accent)]">
                                    <Zap className="w-6 h-6" />
                                </div>
                                <h3 className="text-xl font-bold mb-3" style={{ color: 'var(--nm-text)' }}>{t('about.cards.action.title')}</h3>
                                <p className="leading-relaxed text-sm" style={{ color: 'var(--nm-text-muted)' }}>
                                    {t('about.cards.action.desc')}
                                </p>
                            </div>

                        </div>

                        <div className="text-center pt-8 pb-12">
                            <Link href="/landing#contact" className="inline-flex items-center justify-center px-8 py-4 rounded-full font-bold transition-all duration-300 nm-raised hover:nm-raised-xl active:nm-inset" style={{ color: 'var(--nm-text)', background: 'var(--nm-base)' }}>
                                <span className="mr-2 font-mono">✉</span> {t('about.cta')}
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
