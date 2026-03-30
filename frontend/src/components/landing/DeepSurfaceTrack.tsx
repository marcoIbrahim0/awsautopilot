'use client';

import React, { useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { Shield, Hammer, Rocket, MousePointerClick, Lightbulb, Layers, Verified, ShieldCheck, Cloud, ArrowRight } from 'lucide-react';
import { useLanguage } from '@/lib/i18n';

export function DeepSurfaceTrack() {
    const { t } = useLanguage();
    const targetRef = useRef<HTMLDivElement>(null);
    const { scrollYProgress } = useScroll({
        target: targetRef,
    });

    const continuousScale = useTransform(
        scrollYProgress,
        [0, 1],
        [1, 1.15]
    );

    // Transform vertical scroll to horizontal movement
    // -66.666% because we have 3 screens (0, -33.333, -66.666)
    const x = useTransform(scrollYProgress, [0, 1], ["0%", "-66.666%"]);

    // Parallax/Scale for debossed background text
    const getDebossedStyle = (index: number) => {
        // Each section takes 1/3 of the total progress
        const step = 1 / 3;
        const start = index * step;
        const end = (index + 1) * step;

        // eslint-disable-next-line react-hooks/rules-of-hooks
        const opacity = useTransform(
            scrollYProgress,
            [start - 0.1, start, end, end + 0.1],
            [0, 0.15, 0.15, 0]
        );

        // eslint-disable-next-line react-hooks/rules-of-hooks
        const scale = useTransform(
            scrollYProgress,
            [start, end],
            [1, 1.1]
        );

        return { opacity, scale };
    };

    return (
        <section ref={targetRef} className="relative h-[300vh] landing-neumorphic" style={{ background: '#E7E9EF', '--nm-base': '#E7E9EF' } as React.CSSProperties}>
            <div className="sticky top-0 h-screen overflow-hidden">
                <motion.div style={{ x, willChange: 'transform' }} className="relative flex h-full w-[300vw]">

                    {/* CONTINUOUS BACKGROUND TEXT FOR ALL 3 SCREENS (Hidden on Mobile for Performance) */}
                    <div className="absolute top-0 left-0 w-[300vw] h-full hidden md:flex items-center justify-start pointer-events-none z-0 overflow-hidden pl-10">
                        <motion.div
                            style={{
                                opacity: 0.20,
                                scale: continuousScale,
                                color: '#b9c6d6',
                                transformOrigin: 'left center',
                                willChange: 'transform'
                            }}
                            className="font-ds-arch text-[17.5vw] leading-none select-none whitespace-nowrap [text-shadow:4px_4px_8px_var(--nm-shadow-light),-4px_-4px_8px_var(--nm-shadow-dark)]"
                        >
                            {t('deepSurface.background')}
                        </motion.div>
                    </div>

                    {/* SCREEN 1: SECURITY SIMPLIFIED */}
                    <div className="relative flex h-full w-screen shrink-0 items-center justify-center p-20 overflow-hidden">
                        <div className="relative z-10 text-center max-w-4xl">
                            <h1 className="text-6xl md:text-8xl font-black leading-tight mb-6 tracking-tighter text-[var(--nm-text)]">
                                {t('deepSurface.screen1.title')}<span className="text-[var(--nm-accent)]">{t('deepSurface.screen1.highlight')}</span>
                            </h1>
                            <p className="text-xl md:text-2xl text-[var(--nm-text-muted)] mb-10 max-w-2xl mx-auto leading-relaxed font-ds-body">
                                {t('deepSurface.screen1.desc')}
                            </p>
                            <div className="flex justify-center">
                                <button
                                    onClick={() => window.open('https://calendly.com/maromaher54/30min', '_blank')}
                                    className="nm-neu-flat px-10 py-5 rounded-2xl font-bold text-lg text-[var(--nm-text)] hover:text-[var(--nm-accent)] transition-colors neumorphic-pill"
                                >
                                    {t('deepSurface.screen1.cta')}
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* SCREEN 2: THE BUILD SEQUENCE */}
                    <div className="relative flex h-full w-screen shrink-0 items-center justify-center p-4 md:p-20 overflow-hidden">
                        <div className="relative z-10 w-full max-w-6xl">
                            <div className="mb-8 md:mb-20 text-center">
                                <h2 className="text-3xl md:text-6xl font-bold mb-2 md:mb-4 text-[var(--nm-text)]">{t('deepSurface.screen2.title')}</h2>
                                <p className="text-[var(--nm-text-muted)] text-base md:text-xl">{t('deepSurface.screen2.subtitle')}</p>
                            </div>

                            <div className="flex flex-col md:flex-row items-center justify-between relative px-2 md:px-20 gap-8 md:gap-0">
                                {/* Desktop Horizontal Line */}
                                <div className="hidden md:block absolute top-14 left-40 right-40 h-3 nm-neu-pressed -translate-y-1/2 rounded-full z-0" />
                                {/* Mobile Vertical Line */}
                                <div className="md:hidden absolute top-10 bottom-10 left-1/2 w-2 nm-neu-pressed -translate-x-1/2 rounded-full z-0" />

                                <div className="relative z-10 flex flex-col items-center gap-2 md:gap-8">
                                    <div className="w-20 h-20 md:w-28 md:h-28 rounded-full nm-neu-flat flex items-center justify-center bg-[var(--nm-base)]">
                                        <Shield className="w-8 h-8 md:w-12 md:h-12 text-[var(--nm-accent)]" />
                                    </div>
                                    <div className="text-center bg-[var(--nm-base)]/80 md:backdrop-blur-sm px-3 md:px-4 py-1 md:py-2 rounded-xl">
                                        <h3 className="font-bold text-lg md:text-2xl text-[var(--nm-text)]">{t('deepSurface.screen2.step1.title')}</h3>
                                        <p className="text-[var(--nm-text-muted)] text-xs md:text-base">{t('deepSurface.screen2.step1.desc')}</p>
                                    </div>
                                </div>

                                <div className="relative z-10 flex flex-col items-center gap-2 md:gap-8">
                                    <div className="w-20 h-20 md:w-28 md:h-28 rounded-full nm-neu-flat flex items-center justify-center outline outline-4 md:outline-8 outline-[var(--nm-accent)]/10 bg-[var(--nm-base)]">
                                        <Hammer className="w-8 h-8 md:w-12 md:h-12 text-[var(--nm-accent)]" />
                                    </div>
                                    <div className="text-center bg-[var(--nm-base)]/80 md:backdrop-blur-sm px-3 md:px-4 py-1 md:py-2 rounded-xl">
                                        <h3 className="font-bold text-lg md:text-2xl text-[var(--nm-text)]">{t('deepSurface.screen2.step2.title')}</h3>
                                        <p className="text-[var(--nm-text-muted)] text-xs md:text-base">{t('deepSurface.screen2.step2.desc')}</p>
                                    </div>
                                </div>

                                <div className="relative z-10 flex flex-col items-center gap-2 md:gap-8">
                                    <div className="w-20 h-20 md:w-28 md:h-28 rounded-full nm-neu-flat flex items-center justify-center bg-[var(--nm-base)]">
                                        <Rocket className="w-8 h-8 md:w-12 md:h-12 text-[var(--nm-accent)]" />
                                    </div>
                                    <div className="text-center bg-[var(--nm-base)]/80 md:backdrop-blur-sm px-3 md:px-4 py-1 md:py-2 rounded-xl">
                                        <h3 className="font-bold text-lg md:text-2xl text-[var(--nm-text)]">{t('deepSurface.screen2.step3.title')}</h3>
                                        <p className="text-[var(--nm-text-muted)] text-xs md:text-base">{t('deepSurface.screen2.step3.desc')}</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* SCREEN 3: THE CALL TO ACTION */}
                    <div className="relative flex h-full w-screen shrink-0 items-center justify-center px-4 md:px-20 py-12 overflow-hidden">
                        <div className="relative z-10 text-center py-8 md:p-32 max-w-5xl w-full">
                            <h2 className="text-4xl sm:text-5xl md:text-8xl font-black mb-6 md:mb-8 tracking-tighter text-[var(--nm-text)]">
                                {t('deepSurface.screen3.title').split('{br}')[0]} <br className="sm:hidden" /><span className="text-[var(--nm-accent)] italic">{t('deepSurface.screen3.title').split('{br}')[1]}</span>
                            </h2>
                            <p className="text-base sm:text-lg md:text-2xl text-[var(--nm-text-muted)] mb-8 md:mb-14 max-w-2xl mx-auto px-4">
                                {t('deepSurface.screen3.desc')}
                            </p>

                            <button
                                onClick={() => window.open('https://calendly.com/maromaher54/30min', '_blank')}
                                className="nm-neu-flat bg-[var(--nm-base)] text-[var(--nm-accent)] px-6 md:px-14 py-4 md:py-8 rounded-full text-base sm:text-xl md:text-2xl font-bold flex items-center justify-center gap-3 md:gap-4 mx-auto hover:bg-[var(--nm-accent)] hover:text-white transition-all neumorphic-pill group w-11/12 sm:w-auto"
                            >
                                <span>{t('deepSurface.screen3.cta')}</span>
                                <ArrowRight className="w-5 h-5 md:w-8 md:h-8 group-hover:translate-x-2 md:group-hover:translate-x-3 transition-transform duration-300 shrink-0" />
                            </button>

                            <div className="mt-16 flex flex-wrap justify-center gap-8 md:gap-12 opacity-40 grayscale hover:grayscale-0 transition-all duration-500">
                                <div className="flex items-center gap-3">
                                    <Verified className="w-6 h-6 md:w-7 md:h-7" />
                                    <span className="font-bold tracking-widest text-xs md:text-sm">{t('deepSurface.screen3.badges.soc2')}</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    <ShieldCheck className="w-6 h-6 md:w-7 md:h-7" />
                                    <span className="font-bold tracking-widest text-xs md:text-sm">{t('deepSurface.screen3.badges.iso')}</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    <Cloud className="w-6 h-6 md:w-7 md:h-7" />
                                    <span className="font-bold tracking-widest text-xs md:text-sm">{t('deepSurface.screen3.badges.saas')}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                </motion.div>
            </div>

            <style jsx>{`
                .font-ds-arch {
                    font-family: 'Anton', sans-serif;
                    color: var(--nm-base-dark);
                    text-shadow: 2px 2px 3px var(--nm-shadow-light), -1px -1px 3px var(--nm-shadow-dark);
                }
            `}</style>
        </section>
    );
}
