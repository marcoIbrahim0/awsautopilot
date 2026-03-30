"use client";

import React from "react";
import { motion } from "motion/react";
import { FileCheck, Wrench, Zap } from "lucide-react";
import { useLanguage } from '@/lib/i18n';

const cardStyle = {
    borderRadius: '3rem',
    background: 'var(--nm-base)',
    boxShadow: '4px 4px 24px var(--nm-shadow-dark), -4px -4px 24px var(--nm-shadow-light)',
    border: '1.5px solid rgba(255,255,255,0.45)'
} as const;

const VisualExtraction = () => (
    <div className="absolute top-0 right-0 w-[60%] md:w-[55%] h-[280px] pointer-events-none overflow-hidden opacity-80" style={{ maskImage: 'linear-gradient(to right, transparent, black 35%, black 75%, transparent)', WebkitMaskImage: 'linear-gradient(to right, transparent, black 35%, black 75%, transparent)' }}>
        <div className="absolute inset-y-0 right-0 w-full flex flex-col justify-center gap-4 p-4 font-sans font-medium text-[11px] transform rotate-[-4deg] translate-x-3">
            <div className="flex items-center gap-2 text-red-500/80">
                <span className="w-2 h-2 rounded-full bg-red-500/50 animate-pulse" />
                1,429 Raw Warnings
            </div>
            <div className="flex flex-col gap-1 pl-4 border-l-2 border-white/10 ml-1">
                <motion.div animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 2.5, repeat: Infinity }} className="opacity-60" style={{ color: 'var(--nm-text)' }}>Removing duplicates...</motion.div>
                <motion.div animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 2.5, delay: 0.8, repeat: Infinity }} className="opacity-60" style={{ color: 'var(--nm-text)' }}>Finding root cause...</motion.div>
            </div>
            <motion.div initial={{ scale: 0.95, opacity: 0.8 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 1.5, repeat: Infinity, repeatType: "reverse" }}
                className="flex items-center gap-2 font-bold px-3 py-1.5 rounded-md w-max" style={{ color: 'var(--nm-accent)', background: 'rgba(var(--nm-accent-rgb, 59,130,246),0.1)' }}>
                <Zap className="w-3 h-3" /> 5 Actionable Fixes
            </motion.div>
        </div>
    </div>
);

const VisualCures = () => (
    <div className="absolute top-0 right-0 w-[55%] md:w-[52%] h-[280px] pointer-events-none overflow-hidden opacity-70" style={{ maskImage: 'linear-gradient(to right, transparent, black 35%, black 75%, transparent)', WebkitMaskImage: 'linear-gradient(to right, transparent, black 35%, black 75%, transparent)' }}>
        <div className="absolute inset-y-0 right-0 w-full flex flex-col justify-center gap-3 p-4 font-sans font-medium text-[12px] transform rotate-[4deg] translate-x-2">
            <div className="text-red-400/80 flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-red-400/80" />Vulnerability Detected</div>
            <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 2, repeat: Infinity }} className="pl-4 border-l-2 border-white/10 ml-1 py-1" style={{ color: 'var(--nm-accent)' }}>Generating fix...</motion.div>
            <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6, repeat: Infinity, repeatType: "reverse", repeatDelay: 2.2 }}
                className="text-green-500/90 font-bold flex items-center gap-2 bg-green-500/10 px-2 py-1.5 rounded w-max">
                <span className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" />Environment Secured
            </motion.div>
        </div>
    </div>
);

const VisualAudit = () => (
    <div className="absolute top-0 right-0 w-[55%] md:w-[48%] h-[280px] pointer-events-none overflow-hidden opacity-70" style={{ maskImage: 'linear-gradient(to right, transparent, black 25%, black 70%, transparent)', WebkitMaskImage: 'linear-gradient(to right, transparent, black 25%, black 70%, transparent)' }}>
        <div className="absolute inset-y-0 right-0 w-full flex flex-col justify-center p-4 font-mono text-[9px] leading-relaxed transform scale-110 translate-x-4">
            <div className="opacity-60" style={{ color: 'var(--nm-text)' }}>&quot;evidence&quot;: {"{"}</div>
            <div className="pl-2" style={{ color: 'var(--nm-accent)' }}>&quot;standard&quot;: &quot;SOC2&quot;,</div>
            <div className="pl-2" style={{ color: 'var(--nm-accent)' }}>&quot;control&quot;: &quot;CC6.1&quot;,</div>
            <div className="pl-2 text-green-600/90">&quot;status&quot;: &quot;PASSED&quot;,</div>
            <div className="pl-2 opacity-60" style={{ color: 'var(--nm-text)' }}>&quot;timestamp&quot;:</div>
            <motion.div animate={{ opacity: [0.5, 1, 0.5] }} transition={{ duration: 2.2, repeat: Infinity }} className="text-amber-500 pl-4">&quot;2026-03-03T17:42Z&quot;</motion.div>
            <div className="opacity-60" style={{ color: 'var(--nm-text)' }}>{"}"}</div>
        </div>
    </div>
);

export function BentoIntroGrid() {
    const { t } = useLanguage();

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-10 w-full max-w-7xl mx-auto mt-16 px-6">
            {/* Card 1 */}
            <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} transition={{ duration: 0.5, delay: 0.1 }}
                className="relative md:col-span-2 lg:col-span-1 min-h-[300px] md:min-h-[340px] p-8 md:p-10 block overflow-hidden group"
                style={cardStyle}>
                <VisualExtraction />
                <div className="float-right w-[45%] lg:w-[45%] h-[110px] md:h-[230px] shape-outside-[margin-box]" />
                <div className="relative z-10 w-full">
                    <div className="mb-6 md:mb-8 nm-icon-well h-14 w-14 flex items-center justify-center">
                        <Zap className="h-7 w-7" style={{ color: 'var(--nm-accent)' }} />
                    </div>
                    <h3 className="mb-4 text-2xl font-bold tracking-tight" style={{ color: 'var(--nm-text)' }}>{t('autopilot.cards.signal.title')}</h3>
                    <p className="text-base leading-relaxed opacity-70 inline" style={{ color: 'var(--nm-text)' }}>{t('autopilot.cards.signal.desc')}</p>
                </div>
            </motion.div>

            {/* Card 2 */}
            <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} transition={{ duration: 0.5, delay: 0.2 }}
                className="relative min-h-[300px] md:min-h-[340px] p-8 md:p-10 block overflow-hidden group"
                style={cardStyle}>
                <VisualCures />
                <div className="float-right w-[43%] lg:w-[43%] h-[110px] md:h-[230px] shape-outside-[margin-box]" />
                <div className="relative z-10 w-full">
                    <div className="mb-6 md:mb-8 nm-icon-well h-14 w-14 flex items-center justify-center">
                        <Wrench className="h-7 w-7" style={{ color: 'var(--nm-accent)' }} />
                    </div>
                    <h3 className="mb-4 text-2xl font-bold tracking-tight" style={{ color: 'var(--nm-text)' }}>{t('autopilot.cards.cures.title')}</h3>
                    <p className="text-base leading-relaxed opacity-70 inline" style={{ color: 'var(--nm-text)' }}>{t('autopilot.cards.cures.desc')}</p>
                </div>
            </motion.div>

            {/* Card 3 */}
            <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} transition={{ duration: 0.5, delay: 0.3 }}
                className="relative min-h-[300px] md:min-h-[340px] p-8 md:p-10 block overflow-hidden group"
                style={cardStyle}>
                <VisualAudit />
                <div className="float-right w-[46%] lg:w-[40%] h-[110px] md:h-[230px] shape-outside-[margin-box]" />
                <div className="relative z-10 w-full">
                    <div className="mb-6 md:mb-8 nm-icon-well h-14 w-14 flex items-center justify-center">
                        <FileCheck className="h-7 w-7 text-green-600/80" />
                    </div>
                    <h3 className="mb-4 text-2xl font-bold tracking-tight" style={{ color: 'var(--nm-text)' }}>{t('autopilot.cards.compliance.title')}</h3>
                    <p className="text-base leading-relaxed opacity-70 inline" style={{ color: 'var(--nm-text)' }}>{t('autopilot.cards.compliance.desc')}</p>
                </div>
            </motion.div>
        </div>
    );
}
