'use client';

import Link from 'next/link';
import { SiteNav } from '@/components/site-nav';
import { SectionAnimator } from '@/components/landing/SectionAnimator';
import { MarketingFooter } from '@/components/landing/MarketingFooter';

import { useLanguage } from '@/lib/i18n';

export default function FAQPage() {
    const { t } = useLanguage();

    const FAQ_ITEMS = [
        { q: t('faqPage.items.q1'), a: t('faqPage.items.a1') },
        { q: t('faqPage.items.q2'), a: t('faqPage.items.a2') },
        { q: t('faqPage.items.q3'), a: t('faqPage.items.a3') },
        { q: t('faqPage.items.q4'), a: t('faqPage.items.a4') },
        { q: t('faqPage.items.q5'), a: t('faqPage.items.a5') },
        { q: t('faqPage.items.q6'), a: t('faqPage.items.a6') },
        { q: t('faqPage.items.q7'), a: t('faqPage.items.a7') },
    ];

    return (
        <>
            <SiteNav />
            <main className="landing-neumorphic min-h-screen font-sans">

                {/* Hero Section */}
                <section className="relative z-10 pt-32 pb-16 px-6 text-center">
                    <div className="max-w-4xl mx-auto">
                        <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)] mx-auto" aria-hidden />
                        <span className="font-semibold tracking-widest uppercase text-sm mb-4 block" style={{ color: 'var(--accent)' }}>{t('faqPage.hero.label')}</span>
                        <h1 className="text-4xl md:text-6xl font-bold mb-6 tracking-tight" style={{ color: 'var(--nm-text)' }}>
                            {t('faqPage.hero.title')}
                        </h1>
                        <p className="text-xl max-w-2xl mx-auto leading-relaxed" style={{ color: 'var(--nm-text-muted)' }}>
                            {t('faqPage.hero.desc')}
                        </p>
                    </div>
                </section>

                {/* Content */}
                <section className="relative z-10 border-0 bg-transparent px-6 py-12">
                    <div className="mx-auto max-w-4xl space-y-4">
                        {FAQ_ITEMS.map((item) => (
                            <details
                                key={item.q}
                                className="group nm-raised-sm p-6 sm:p-7"
                            >
                                <summary className="flex cursor-pointer list-none items-center gap-4 text-left outline-none marker:content-none [&::-webkit-details-marker]:hidden">
                                    <span className="nm-icon-well relative flex h-9 w-9 shrink-0 items-center justify-center text-[var(--accent)] transition duration-300 group-open:scale-[1.06]">
                                        <span className="absolute h-[2px] w-4 rounded-full bg-[var(--accent)] transition-all duration-300 ease-out group-open:w-[18px]" />
                                        <span className="absolute h-4 w-[2px] rounded-full bg-[var(--accent)] transition-all duration-300 ease-out group-open:scale-y-0 group-open:rotate-90" />
                                    </span>
                                    <span className="text-xl font-semibold transition-colors duration-300 sm:text-2xl" style={{ color: 'var(--nm-text)' }}>
                                        {item.q}
                                    </span>
                                </summary>
                                <div className="faq-panel">
                                    <div className="overflow-hidden">
                                        <p className="faq-answer mt-3 text-base sm:text-lg pl-13" style={{ color: 'var(--nm-text-muted)' }}>
                                            {item.a}
                                        </p>
                                    </div>
                                </div>
                            </details>
                        ))}

                        <div className="text-center pt-16 pb-12">
                            <p className="text-lg text-[var(--nm-text-muted)] mb-8">
                                {t('faqPage.contact.desc')} <a href="mailto:support@ocypheris.com" className="text-[var(--accent)] font-semibold hover:underline">support@ocypheris.com</a>
                            </p>
                            <Link href="/landing#contact" className="inline-flex items-center justify-center px-8 py-4 rounded-full font-bold transition-all duration-300 nm-raised hover:nm-raised-xl active:nm-inset" style={{ color: 'var(--nm-text)', background: 'var(--nm-base)' }}>
                                <span className="mr-2 font-mono">←</span> {t('faqPage.contact.cta')}
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
