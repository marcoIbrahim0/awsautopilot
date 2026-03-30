'use client';

import React, { useState } from 'react';
import { motion, useScroll, useTransform, AnimatePresence } from 'motion/react';
import { Shield, Wrench, ArrowRight } from 'lucide-react';

export function DeepSurfaceSection() {
    const { scrollYProgress } = useScroll();
    const ySecurity = useTransform(scrollYProgress, [0, 1], ['0%', '20%']);
    const opacitySecurity = useTransform(scrollYProgress, [0, 0.4, 0.6], [0.4, 0.3, 0]);

    const yDeployment = useTransform(scrollYProgress, [0.3, 1], ['60%', '0%']);
    const opacityDeployment = useTransform(scrollYProgress, [0.3, 0.5, 1], [0, 0.3, 0.5]);

    const [expandedService, setExpandedService] = useState<'manual' | 'saas' | null>(null);

    const toggleManual = () => setExpandedService(prev => prev === 'manual' ? null : 'manual');
    const toggleSaas = () => setExpandedService(prev => prev === 'saas' ? null : 'saas');

    return (
        <section className="relative w-full min-h-screen bg-ds-bg text-ds-text-primary overflow-hidden font-ds-body z-10 py-32" id="services">
            {/* Background Architectural Text */}
            <div className="absolute inset-0 pointer-events-none flex flex-col justify-between overflow-hidden z-0">
                <motion.div
                    className="absolute top-[10%] left-[-2%] font-ds-arch text-[25vw] leading-[0.8] tracking-tight select-none opacity-40 mix-blend-multiply"
                    style={{
                        y: ySecurity,
                        opacity: opacitySecurity,
                        color: 'transparent',
                        WebkitTextStroke: '2px rgba(195, 201, 214, 0.5)',
                        textShadow: '4px 4px 8px rgba(255,255,255,1), -4px -4px 8px rgba(195,201,214,0.6)'
                    }}
                >
                    SECURITY
                </motion.div>

                <motion.div
                    className="absolute bottom-[-5%] right-[-2%] font-ds-arch text-[22vw] leading-[0.8] tracking-tight select-none opacity-40 mix-blend-multiply"
                    style={{
                        y: yDeployment,
                        opacity: opacityDeployment,
                        color: 'transparent',
                        WebkitTextStroke: '2px rgba(195, 201, 214, 0.5)',
                        textShadow: '4px 4px 8px rgba(255,255,255,1), -4px -4px 8px rgba(195,201,214,0.6)'
                    }}
                >
                    DEPLOYMENT
                </motion.div>
            </div>

            <div className="relative z-10 max-w-7xl mx-auto px-6 h-full flex flex-col justify-center">
                {/* Header */}
                <div className="flex flex-col items-center justify-center text-center mb-36">
                    <div className="mb-4 h-[2px] w-12 bg-[var(--nm-accent)] rounded-full"></div>

                    <span className="font-ds-mono text-sm uppercase tracking-[0.15em] text-[var(--nm-accent)] mb-4 font-bold">
                        Beyond automation
                    </span>

                    <h2 className="text-4xl md:text-5xl lg:text-6xl font-ds-head font-bold text-[var(--nm-text)] mb-6 tracking-tight max-w-3xl">
                        We Design, Build &amp; Deploy Your Secure Application
                    </h2>
                    <p className="text-lg md:text-xl text-ds-text-secondary max-w-2xl leading-relaxed">
                        Whether you&apos;re launching a SaaS product or hardening an existing AWS environment, our team takes ownership of security from the first line of architecture to production release.
                    </p>
                </div>

                {/* Foreground Layout */}
                <div className="flex flex-col gap-32 w-full mb-40 lg:mb-48">

                    {/* Service 1: Security Architecture & Audit */}
                    <div className="w-full md:w-[60%] lg:w-[45%] md:ml-auto">
                        <motion.div
                            className="p-8 md:p-10 rounded-[2rem] transition-all duration-500 cursor-pointer bg-ds-bg shadow-ds-float hover:shadow-ds-pressed group"
                            onClick={toggleManual}
                        >
                            <div className="flex items-start gap-6">
                                {/* Convex Icon Wrapper */}
                                <div className="w-16 h-16 rounded-full flex items-center justify-center shrink-0 bg-ds-bg shadow-ds-float group-hover:shadow-ds-pressed transition-all duration-500">
                                    <Shield className="w-7 h-7 text-ds-text-secondary group-hover:text-ds-accent transition-colors duration-500" />
                                </div>
                                <div>
                                    <h3 className="text-2xl lg:text-3xl font-ds-head font-bold text-ds-text-primary mb-3 mt-1">
                                        Security Architecture &amp; Audit
                                    </h3>
                                    <p className="text-ds-text-secondary text-base lg:text-lg leading-relaxed">
                                        Our architects assess your current posture, design a hardened AWS environment from scratch, and deliver a prioritised remediation roadmap — so every layer of your stack is built on solid security foundations.
                                    </p>
                                </div>
                            </div>

                            {/* The Tactile Detail Expansion */}
                            <AnimatePresence>
                                {expandedService === 'manual' && (
                                    <motion.div
                                        initial={{ height: 0, opacity: 0 }}
                                        animate={{ height: 'auto', opacity: 1 }}
                                        exit={{ height: 0, opacity: 0 }}
                                        className="overflow-hidden"
                                    >
                                        <div className="pt-8 pl-22">
                                            <ul className="space-y-4">
                                                {['Threat modelling & architecture review', 'Hands-on AWS environment hardening', 'Prioritised findings with actionable fixes'].map((item, i) => (
                                                    <motion.li
                                                        key={i}
                                                        initial={{ y: 20, opacity: 0 }}
                                                        animate={{ y: 0, opacity: 1 }}
                                                        exit={{ opacity: 0 }}
                                                        transition={{ delay: i * 0.1, duration: 0.4 }}
                                                        className="flex items-center gap-4 text-ds-text-secondary font-medium text-lg"
                                                    >
                                                        <div className="w-2.5 h-2.5 rounded-full shadow-ds-debossed bg-ds-bg shrink-0" />
                                                        {item}
                                                    </motion.li>
                                                ))}
                                            </ul>
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </motion.div>
                    </div>

                    {/* Service 2: End-to-End Secure SaaS Delivery */}
                    <div className="w-full md:w-[60%] lg:w-[45%]">
                        <motion.div
                            className="p-8 md:p-10 rounded-[2rem] transition-all duration-500 cursor-pointer bg-ds-bg shadow-ds-float hover:shadow-ds-pressed group"
                            onClick={toggleSaas}
                        >
                            <div className="flex items-start gap-6">
                                <div className="w-16 h-16 rounded-full flex items-center justify-center shrink-0 bg-ds-bg shadow-ds-float group-hover:shadow-ds-pressed transition-all duration-500">
                                    <Wrench className="w-7 h-7 text-ds-text-secondary group-hover:text-ds-accent transition-colors duration-500" />
                                </div>
                                <div>
                                    <div className="inline-block px-4 py-1 bg-ds-bg shadow-ds-pressed rounded-full mb-4">
                                        <span className="text-ds-accent font-ds-mono text-[11px] font-bold uppercase tracking-[0.15em]">
                                            Built Secure from Day One
                                        </span>
                                    </div>
                                    <h3 className="text-2xl lg:text-3xl font-ds-head font-bold text-ds-text-primary mb-3">
                                        End-to-End Secure SaaS Delivery
                                    </h3>
                                    <p className="text-ds-text-secondary text-base lg:text-lg leading-relaxed">
                                        Tell us what you&apos;re building. We handle the rest — from secure AWS architecture design and implementation to a production-ready deployment, with enterprise-grade security and compliance baked into every phase.
                                    </p>
                                </div>
                            </div>

                            {/* The Build Sequence Expansion */}
                            <AnimatePresence>
                                {expandedService === 'saas' && (
                                    <motion.div
                                        initial={{ height: 0, opacity: 0 }}
                                        animate={{ height: 'auto', opacity: 1 }}
                                        exit={{ height: 0, opacity: 0 }}
                                        className="overflow-hidden"
                                    >
                                        <div className="pt-10 pl-[84px] relative">
                                            {/* Engraved Line container */}
                                            <div className="absolute left-[39px] top-[50px] bottom-6 w-[6px] bg-ds-bg shadow-ds-debossed overflow-hidden rounded-full">
                                                <motion.div
                                                    className="w-full h-[80px] bg-ds-accent opacity-60 blur-[3px] rounded-full"
                                                    animate={{ y: ['-100%', '350%'] }}
                                                    transition={{ repeat: Infinity, duration: 2.5, ease: "linear" }}
                                                />
                                            </div>

                                            {/* Nodes */}
                                            <div className="flex flex-col gap-10 relative">
                                                {['Design', 'Implement', 'Deploy'].map((node, i) => (
                                                    <div key={i} className="flex items-center gap-6 relative right-12">
                                                        <div className="w-5 h-5 rounded-full bg-ds-bg shadow-ds-float z-10 border border-white/40" />
                                                        <span className="font-ds-head font-bold text-ds-text-primary text-xl tracking-tight">{node}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </motion.div>
                    </div>

                </div>

                {/* The Call to Action Floor */}
                <div className="flex justify-center mt-auto z-20 pb-12 cursor-pointer">
                    <button
                        onClick={() => window.open('https://calendly.com/maromaher54/30min', '_blank')}
                        className="flex items-center justify-center gap-3 px-10 h-14 rounded-full bg-ds-bg shadow-ds-float hover:shadow-ds-float-hover hover:-translate-y-1 active:shadow-ds-pressed active:-translate-y-0.5 transition-all duration-300 group"
                    >
                        <span className="font-ds-head font-semibold text-ds-accent text-lg group-active:translate-y-[1px]">Book a 20-minute walkthrough</span>
                        <ArrowRight className="w-5 h-5 text-ds-accent group-hover:translate-x-1 group-active:translate-y-[1px] transition-transform" />
                    </button>
                </div>
            </div>
        </section>
    );
}
