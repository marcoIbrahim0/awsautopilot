'use client';

import React from 'react';
import { motion } from 'motion/react';
import { FileDown, CheckCircle2, FileJson, Clock, MousePointer2 } from 'lucide-react';
import { PrimaryCTANeumorphic } from '@/components/ui/PrimaryCTANeumorphic';
import { useLanguage } from '@/lib/i18n';

const CALENDLY_URL = 'https://calendly.com/maromaher54/30min';

export const BaselineReportHighlight = () => {
    const { t } = useLanguage();

    return (
        <section className="relative z-10 px-6 py-16 sm:py-24">
            <div className="mx-auto max-w-7xl">
                {/* Header */}
                <div className="text-center mb-16">
                    <div className="mb-4 h-[3px] w-24 rounded-full mx-auto" style={{ background: 'var(--nm-accent)' }} aria-hidden />
                    <h2 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl" style={{ color: 'var(--nm-text)' }}>
                        {t('baseline.title')}
                    </h2>
                    <p className="mt-4 text-lg max-w-2xl mx-auto" style={{ color: 'var(--nm-text-muted)' }}>
                        {t('baseline.desc')}
                    </p>
                </div>

                {/* Neumorphic container: Edge-to-edge inset well on mobile, raised card on tablet/desktop */}
                <div className="nm-inset md:nm-raised-lg md:nm-inset-none -mx-6 md:mx-0 rounded-none md:rounded-[1rem] overflow-hidden">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-0 relative z-10">
                        {/* Left Side: Features */}
                        <div className="p-8 sm:p-12 flex flex-col justify-center" style={{ borderRight: '1px solid rgba(166,184,207,0.3)' }}>
                            <h3 className="text-2xl font-bold mb-8" style={{ color: 'var(--nm-text)' }}>{t('baseline.card.title')}</h3>
                            <div className="space-y-7">
                                {[
                                    { icon: Clock, title: t('baseline.card.features.clock.title'), desc: t('baseline.card.features.clock.desc') },
                                    { icon: CheckCircle2, title: t('baseline.card.features.check.title'), desc: t('baseline.card.features.check.desc') },
                                    { icon: FileJson, title: t('baseline.card.features.file.title'), desc: t('baseline.card.features.file.desc') }
                                ].map((feature, i) => (
                                    <div key={i} className="flex items-start gap-4">
                                        {/* Raised icon socket on mobile (since bg is inset), inset on desktop */}
                                        <div className="nm-icon-well nm-raised md:nm-inset md:nm-raised-none h-11 w-11 shrink-0 flex items-center justify-center rounded-full">
                                            <feature.icon className="h-5 w-5" style={{ color: 'var(--nm-accent)' }} />
                                        </div>
                                        <div>
                                            <h4 className="text-lg font-semibold" style={{ color: 'var(--nm-text)' }}>{feature.title}</h4>
                                            <p className="text-sm leading-relaxed mt-1" style={{ color: 'var(--nm-text-muted)' }}>{feature.desc}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>

                        </div>

                        {/* Right Side: Report graphic */}
                        {/* On mobile, this will just blend into the inset well. On desktop, it has the base-dark background */}
                        <div className="relative p-8 sm:p-12 flex items-center justify-center min-h-[400px] md:bg-[var(--nm-base-dark)]" style={{ borderTop: '1px solid rgba(166,184,207,0.3)' }}>
                            {/* Neumorphic report card - explicitly raised to sit on top of the inset/dark background */}
                            <div className="nm-raised w-full max-w-sm p-6 bg-[var(--nm-base)]">
                                <div className="flex justify-between items-center mb-6">
                                    <div className="flex items-center gap-2">
                                        {/* Inset icon */}
                                        <div className="nm-icon-well nm-inset h-9 w-9 flex items-center justify-center rounded-full">
                                            <FileDown className="w-4 h-4 text-green-600" />
                                        </div>
                                        <span className="text-sm font-medium" style={{ color: 'var(--nm-text)' }}>Baseline Report</span>
                                    </div>
                                    {/* Status badge: raised pill */}
                                    <span
                                        className="text-xs font-mono px-2 py-1 nm-raised-sm"
                                        style={{ color: 'var(--nm-accent)', fontSize: '0.7rem', borderRadius: '9999px' }}
                                    >
                                        Generated
                                    </span>
                                </div>

                                {/* Animated Checklist */}
                                <div className="space-y-4">
                                    {[
                                        "SOC 2 Controls Mapped",
                                        "ISO 27001 Evidence Gathered",
                                        "CIS Benchmarks Verified"
                                    ].map((text, i) => (
                                        <div key={i} className="flex gap-4 items-center">
                                            {/* Status Icon Indicator */}
                                            <motion.div
                                                className="nm-icon-well nm-inset h-7 w-7 shrink-0 flex items-center justify-center rounded-full"
                                                animate={{
                                                    backgroundColor: [
                                                        'rgba(166,184,207,0.1)', // Initial (waiting)
                                                        'transparent',           // During progress (track shows instead)
                                                        'rgba(34,197,94,0.1)',   // Done (green background)
                                                        'rgba(34,197,94,0.1)',   // Hold
                                                        'rgba(166,184,207,0.1)', // Reset
                                                    ]
                                                }}
                                                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                                            >
                                                <motion.div
                                                    animate={{
                                                        opacity: [0, 0, 1, 1, 0] // Only show checkmark when done
                                                    }}
                                                    transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                                                >
                                                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                                                </motion.div>
                                            </motion.div>

                                            <div className="flex-1 space-y-1.5 mt-0.5">
                                                <div className="flex justify-between items-center text-sm font-medium" style={{ color: 'var(--nm-text-muted)' }}>
                                                    <span>{text}</span>
                                                </div>
                                                {/* Mini progress bar track */}
                                                <div className="nm-progress-track nm-inset h-1 w-full rounded-full overflow-hidden">
                                                    <motion.div
                                                        className="nm-progress-fill h-full bg-[var(--nm-accent)]"
                                                        initial={{ width: "0%" }}
                                                        animate={{
                                                            width: [
                                                                "0%", // 0-1s: Waiting
                                                                i === 0 ? "100%" : "0%", // Element 0 fills 1s-2s
                                                                i <= 1 ? "100%" : "0%", // Element 1 fills 2s-3s
                                                                "100%", // Element 2 fills 3s-4s
                                                                "100%", // 4s-7s: Hold full
                                                                "0%"    // 7s-8s: Reset
                                                            ]
                                                        }}
                                                        transition={{ duration: 8, ease: "easeInOut", repeat: Infinity, times: [0, 0.25, 0.375, 0.5, 0.85, 1] }}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {/* Export button & Animated Cursor */}
                                <div className="mt-8 pt-6 relative" style={{ borderTop: '1px solid rgba(166,184,207,0.4)' }}>

                                    {/* The Button */}
                                    <motion.div
                                        animate={{
                                            scale: [1, 1, 1, 0.95, 1, 1],
                                            backgroundColor: [
                                                'var(--nm-base)',
                                                'var(--nm-base)',
                                                'var(--nm-base)',
                                                'var(--nm-accent)',
                                                'var(--nm-base)',
                                                'var(--nm-base)'
                                            ],
                                            color: [
                                                'var(--nm-accent)',
                                                'var(--nm-accent)',
                                                'var(--nm-accent)',
                                                '#ffffff',
                                                'var(--nm-accent)',
                                                'var(--nm-accent)'
                                            ]
                                        }}
                                        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut", times: [0, 0.6, 0.65, 0.7, 0.8, 1] }}
                                        className="nm-raised-sm flex items-center justify-center cursor-pointer relative z-10 mx-auto w-3/4 overflow-hidden"
                                        style={{ height: '3rem', borderRadius: '1rem' }}
                                    >
                                        <span className="text-sm font-bold relative z-10">Export SOC 2 Evidence</span>

                                        {/* The Animated Cursor (Nested inside the button for perfect centering) */}
                                        <motion.div
                                            className="absolute z-20 pointer-events-none drop-shadow-md"
                                            animate={{
                                                x: [100, 100, 0, 0, 100, 100],       // Zip in from right/bottom to the exact center origin
                                                y: [50, 50, 0, 0, 50, 50],
                                                scale: [1, 1, 1, 0.8, 1, 1],         // Clicks down at 0.7s mark
                                                opacity: [0, 0, 1, 1, 1, 0]          // Now stays visible until step 5 (0.8s), then fades to 0 by step 6 (1.0s)
                                            }}
                                            transition={{ duration: 8, repeat: Infinity, ease: "easeInOut", times: [0, 0.55, 0.65, 0.7, 0.8, 1] }}
                                            style={{ left: '50%', top: '50%' }}
                                        >
                                            <MousePointer2 className="w-5 h-5 text-white fill-black" strokeWidth={1.5} />
                                        </motion.div>
                                    </motion.div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Centered CTA below the grid */}
                <div className="mt-12 sm:mt-16 flex justify-center">
                    <PrimaryCTANeumorphic href={CALENDLY_URL} text={t('hero.cta')} />
                </div>
            </div>
        </section>
    );
};
