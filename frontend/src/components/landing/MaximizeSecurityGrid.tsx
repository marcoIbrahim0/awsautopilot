"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronRight, ChevronLeft } from "lucide-react";
import { useLanguage } from "@/lib/i18n";

const VisualConnect = () => (
    <div className="w-full h-full p-2 sm:p-4 md:p-8 flex items-center justify-center">
        <div className="w-full max-w-[240px] xs:max-w-[260px] sm:max-w-sm flex flex-col overflow-hidden scale-[0.9] xs:scale-100 transition-transform"
            style={{
                borderRadius: '3rem',
                background: 'var(--nm-base)',
                boxShadow: '4px 4px 24px var(--nm-shadow-dark), -4px -4px 24px var(--nm-shadow-light)',
                border: '1.5px solid rgba(255,255,255,0.45)'
            }}>
            <div className="flex items-center justify-between px-5 py-3.5 bg-white/5">
                <div className="flex items-center gap-2">
                    <div className="hidden sm:block w-2.5 h-2.5 rounded-full bg-red-400/80" />
                    <div className="hidden sm:block w-2.5 h-2.5 rounded-full bg-yellow-400/80" />
                    <div className="hidden sm:block w-2.5 h-2.5 rounded-full bg-green-400/80" />
                    <span className="ml-2 text-[10px] sm:text-xs font-mono opacity-60" style={{ color: 'var(--nm-text)' }}>iam_policy.json</span>
                </div>
                <span className="px-2 py-0.5 rounded text-[8px] sm:text-[10px] uppercase font-bold tracking-wider nm-inset-sm text-green-600/80">Read-Only</span>
            </div>

            <div className="p-5 text-[9px] xs:text-[10px] sm:text-xs md:text-sm font-mono leading-relaxed" style={{ color: 'var(--nm-text)' }}>
                <p>{"{"}</p>
                <p className="pl-4"><span style={{ color: 'var(--nm-accent)' }}>&quot;Effect&quot;</span>: <span className="text-green-600">&quot;Allow&quot;</span>,</p>
                <p className="pl-4"><span style={{ color: 'var(--nm-accent)' }}>&quot;Action&quot;</span>: [</p>
                <p className="pl-8 text-amber-600/90">&quot;securityhub:GetFindings&quot;,</p>
                <p className="pl-8 text-amber-600/90">&quot;guardduty:GetFindings&quot;,</p>
                <p className="pl-8 text-amber-600/90">&quot;ec2:DescribeInstances&quot;</p>
                <p className="pl-4">],</p>
                <p className="pl-4"><span style={{ color: 'var(--nm-accent)' }}>&quot;Resource&quot;</span>: <span className="text-green-600">&quot;*&quot;</span></p>
                <p>{"}"}</p>
                <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: "100%" }}
                    transition={{ duration: 1.5, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }}
                    className="mt-6 hidden sm:block h-[2px] opacity-40"
                    style={{ background: 'var(--nm-accent)' }}
                />
            </div>
        </div>
    </div>
);

const VisualVisibility = () => (
    <div className="w-full h-full p-3 sm:p-8 flex items-center justify-center">
        <div className="w-full max-w-[240px] xs:max-w-[260px] sm:max-w-sm flex flex-col overflow-hidden scale-[0.9] xs:scale-100 transition-transform"
            style={{
                borderRadius: '3rem',
                background: 'var(--nm-base)',
                boxShadow: '4px 4px 24px var(--nm-shadow-dark), -4px -4px 24px var(--nm-shadow-light)',
                border: '1.5px solid rgba(255,255,255,0.45)'
            }}>
            <div className="flex items-center gap-3 px-5 py-3.5 bg-white/5">
                <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--nm-accent)', boxShadow: '0 0 8px var(--nm-accent)' }} />
                <span className="text-[10px] sm:text-xs font-mono tracking-widest uppercase opacity-70" style={{ color: 'var(--nm-accent)' }}>EventBridge Stream</span>
            </div>

            <div className="p-5 space-y-4 relative overflow-hidden h-40 sm:h-48">
                <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[var(--nm-base)]" style={{ zIndex: 10 }} />
                {[1, 2, 3, 4].map((i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: [0, 1, 0.4], y: [20, 0, -20] }}
                        transition={{ duration: 2, repeat: Infinity, delay: i * 0.5, ease: "linear" }}
                        className="flex items-start gap-3 border-l-2 border-[var(--nm-accent)]/30 pl-3"
                    >
                        <span className="text-[8px] sm:text-[10px] font-mono whitespace-nowrap pt-0.5 opacity-40" style={{ color: 'var(--nm-text)' }}>EST {10 + i}:42:0{i}</span>
                        <div className="flex-1">
                            <span className="text-[10px] sm:text-xs font-mono font-bold opacity-80" style={{ color: 'var(--nm-accent)' }}>INGEST:</span>
                            <span className="text-[10px] sm:text-xs font-mono ml-2" style={{ color: 'var(--nm-text)' }}>New finding</span>
                        </div>
                    </motion.div>
                ))}
            </div>
        </div>
    </div>
);

const VisualControl = () => (
    <div className="w-full h-full p-2 sm:p-4 md:p-8 flex items-center justify-center">
        <div className="w-full max-w-[240px] xs:max-w-[260px] sm:max-w-sm relative p-5 flex flex-col gap-6 scale-[0.9] xs:scale-100 transition-transform"
            style={{
                borderRadius: '3rem',
                background: 'var(--nm-base)',
                boxShadow: '4px 4px 24px var(--nm-shadow-dark), -4px -4px 24px var(--nm-shadow-light)',
                border: '1.5px solid rgba(255,255,255,0.45)'
            }}>
            <div className="flex items-center justify-between">
                <div className="flex flex-col">
                    <span className="font-semibold text-sm sm:text-lg opacity-90" style={{ color: 'var(--nm-text)' }}>Discovery Mode</span>
                    <span className="text-[10px] sm:text-xs mt-1 opacity-60" style={{ color: 'var(--nm-text)' }}>Read-only account mapping</span>
                </div>
                <div className="w-10 h-5 sm:w-12 sm:h-6 rounded-full nm-inset relative flex items-center">
                    <div className="w-3.5 h-3.5 sm:w-4 sm:h-4 ml-1 rounded-full bg-blue-500/80 shadow-md" />
                </div>
            </div>

            <div className="h-px w-full bg-white/10" />

            <div className="flex items-center justify-between opacity-40">
                <div className="flex flex-col">
                    <h4 className="font-semibold flex items-center gap-2 text-sm sm:text-lg" style={{ color: 'var(--nm-text)' }}>
                        Write Access <span className="text-[8px] sm:text-[10px] uppercase px-1.5 py-0.5 nm-inset-sm font-bold opacity-60">Disabled</span>
                    </h4>
                    <span className="text-[10px] sm:text-xs mt-1" style={{ color: 'var(--nm-text)' }}>Direct infra mutation</span>
                </div>
                <div className="w-10 h-5 sm:w-12 sm:h-6 rounded-full nm-inset relative flex items-center">
                    <div className="w-3.5 h-3.5 sm:w-4 sm:h-4 ml-auto mr-1 rounded-full bg-gray-400/50" />
                </div>
            </div>
        </div>
    </div>
);

function getClosestFeatureIndex(nodes: Array<HTMLDivElement | null>, viewportMidpoint: number) {
    let closestIndex = -1;
    let closestDistance = Number.POSITIVE_INFINITY;

    nodes.forEach((node, index) => {
        if (!node) return;
        const rect = node.getBoundingClientRect();
        const distance = Math.abs(rect.top + rect.height / 2 - viewportMidpoint);
        if (distance < closestDistance) {
            closestDistance = distance;
            closestIndex = index;
        }
    });

    return closestIndex;
}

export function MaximizeSecurityGrid() {
    const { t } = useLanguage();
    const [activeIndex, setActiveIndex] = useState(0);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const desktopFeatureRefs = useRef<Array<HTMLDivElement | null>>([]);
    const [canScrollRight, setCanScrollRight] = useState(true);
    const [canScrollLeft, setCanScrollLeft] = useState(false);

    const FEATURES = [
        {
            title: t('proof.features.connect.title'),
            description: (
                <p dangerouslySetInnerHTML={{ __html: t('proof.features.connect.desc').replace('read-only IAM role', '<span class="font-mono text-sm nm-inset-sm px-1.5 py-0.5" style="color: var(--nm-accent)">read-only IAM role</span>').replace('Read-Only IAM-Rolle', '<span class="font-mono text-sm nm-inset-sm px-1.5 py-0.5" style="color: var(--nm-accent)">Read-Only IAM-Rolle</span>') }} />
            ),
            badge: "ZERO AGENTS",
            visual: VisualConnect
        },
        {
            title: t('proof.features.visibility.title'),
            description: (
                <p dangerouslySetInnerHTML={{ __html: t('proof.features.visibility.desc').replace('EventBridge routing', '<span class="font-mono text-sm nm-inset-sm px-1.5 py-0.5" style="color: var(--nm-accent)">EventBridge routing</span>') }} />
            ),
            badge: "REAL-TIME TRACING",
            visual: VisualVisibility
        },
        {
            title: t('proof.features.control.title'),
            description: (
                <p dangerouslySetInnerHTML={{ __html: t('proof.features.control.desc').replace('verifiable PR bundles', '<span class="font-mono text-sm nm-inset-sm px-1.5 py-0.5" style="color: var(--nm-accent)">verifiable PR bundles</span>').replace('verifizierbare Pull-Request-Bundles', '<span class="font-mono text-sm nm-inset-sm px-1.5 py-0.5" style="color: var(--nm-accent)">verifizierbare Pull-Request-Bundles</span>') }} />
            ),
            badge: "TRUST VERIFIED",
            visual: VisualControl
        }
    ];

    const checkScroll = () => {
        if (scrollContainerRef.current) {
            const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
            setCanScrollLeft(scrollLeft > 10);
            setCanScrollRight(Math.ceil(scrollLeft + clientWidth) < scrollWidth - 10);
        }
    };

    useEffect(() => {
        checkScroll();
        const container = scrollContainerRef.current;
        if (container) {
            container.addEventListener('scroll', checkScroll, { passive: true });
            window.addEventListener('resize', checkScroll, { passive: true });
            return () => {
                container.removeEventListener('scroll', checkScroll);
                window.removeEventListener('resize', checkScroll);
            };
        }
    }, []);

    useEffect(() => {
        const syncDesktopActiveIndex = () => {
            if (window.innerWidth < 1024) return;
            const nextIndex = getClosestFeatureIndex(desktopFeatureRefs.current, window.innerHeight * 0.5);
            if (nextIndex >= 0) {
                setActiveIndex((current) => (current === nextIndex ? current : nextIndex));
            }
        };

        syncDesktopActiveIndex();
        window.addEventListener('scroll', syncDesktopActiveIndex, { passive: true });
        window.addEventListener('resize', syncDesktopActiveIndex, { passive: true });

        return () => {
            window.removeEventListener('scroll', syncDesktopActiveIndex);
            window.removeEventListener('resize', syncDesktopActiveIndex);
        };
    }, []);
    const getScrollAmount = () => scrollContainerRef.current ? scrollContainerRef.current.clientWidth * 0.85 : 0;
    const scrollToNext = () => { scrollContainerRef.current?.scrollBy({ left: getScrollAmount(), behavior: 'smooth' }); };
    const scrollToPrev = () => { scrollContainerRef.current?.scrollBy({ left: -getScrollAmount(), behavior: 'smooth' }); };
    const desktopStickyTopOffset = -48;
    const desktopVisualOffset =
        activeIndex === 0
            ? -100
            : activeIndex === FEATURES.length - 1
                ? 228
                : -40;

    return (
        <div className="relative w-full">
            {/* Mobile View */}
            <div className="block lg:hidden -mx-6 py-8 relative" style={{ background: 'var(--nm-base)' }}>
                <div
                    ref={scrollContainerRef}
                    className="flex overflow-x-auto snap-x snap-mandatory gap-6 px-6 pb-12 pt-4 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]"
                    style={{ scrollPaddingLeft: '1.5rem' }}
                >
                    {FEATURES.map((feature, i) => (
                        <div
                            key={`mobile-${i}`}
                            className="w-[85vw] sm:w-[400px] flex-shrink-0 snap-start flex flex-col overflow-hidden min-w-0"
                            style={{
                                borderRadius: '3rem',
                                background: 'var(--nm-base)',
                                boxShadow: '6px 6px 20px var(--nm-shadow-dark), -6px -6px 20px var(--nm-shadow-light)',
                                border: '1.5px solid rgba(255,255,255,0.45)'
                            }}
                        >
                            <div className="p-6 pb-4">
                                <div className="w-full aspect-[4/3] overflow-hidden nm-inset relative flex items-center justify-center" style={{ borderRadius: '2.25rem' }}>
                                    {React.createElement(feature.visual)}
                                </div>
                            </div>
                            <div className="flex flex-col gap-4 px-6 pb-6">
                                {feature.badge && (
                                    <span className="inline-flex tracking-wider self-start items-center nm-raised-sm px-2.5 py-1 text-[10px] font-bold" style={{ color: 'var(--nm-accent)', borderRadius: '9999px' }}>
                                        {feature.badge}
                                    </span>
                                )}
                                <h3 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--nm-text)' }}>{feature.title}</h3>
                                <div className="text-base leading-relaxed font-medium opacity-70" style={{ color: 'var(--nm-text)' }}>{feature.description}</div>
                            </div>
                        </div>
                    ))}
                </div>

                <AnimatePresence>
                    {canScrollLeft && (
                        <motion.button initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }} transition={{ duration: 0.2 }} onClick={scrollToPrev}
                            className="absolute left-6 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 rounded-full backdrop-blur-md shadow-lg border border-white/20 text-gray-600 hover:text-blue-500 transition-colors z-20" style={{ background: 'var(--nm-base)' }}>
                            <ChevronLeft className="w-5 h-5 pr-0.5" />
                        </motion.button>
                    )}
                </AnimatePresence>
                <AnimatePresence>
                    {canScrollRight && (
                        <motion.button initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }} transition={{ duration: 0.2 }} onClick={scrollToNext}
                            className="absolute right-6 top-1/2 -translate-y-1/2 flex items-center justify-center w-10 h-10 rounded-full backdrop-blur-md shadow-lg border border-white/20 text-gray-600 hover:text-blue-500 transition-colors z-20" style={{ background: 'var(--nm-base)' }}>
                            <ChevronRight className="w-5 h-5 pl-0.5" />
                        </motion.button>
                    )}
                </AnimatePresence>
            </div>

            {/* Desktop View */}
            <div className="hidden lg:flex flex-row max-w-7xl mx-auto px-12 gap-10 xl:gap-14">
                <div className="w-[50%] xl:w-[55%] flex flex-col py-[2vh]">
                    <div aria-hidden="true" className="h-[clamp(11rem,27vh,18rem)]" />
                    {FEATURES.map((feature, i) => (
                        <motion.div
                            key={`desktop-${i}`}
                            ref={(node) => {
                                desktopFeatureRefs.current[i] = node;
                            }}
                            className="min-h-[40vh] flex flex-col justify-center py-3"
                            initial="hidden"
                            whileInView="visible"
                            viewport={{ amount: 0.4, margin: "-10% 0px -10% 0px" }}
                            variants={{ hidden: { opacity: 0.3, y: 20 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5 } } }}
                        >
                            <div className="max-w-xl">
                                {feature.badge && (
                                    <span className="inline-flex tracking-wider items-center nm-raised-sm px-2.5 py-1 text-xs font-bold shadow-sm mb-6" style={{ color: 'var(--nm-accent)', borderRadius: '9999px' }}>
                                        {feature.badge}
                                    </span>
                                )}
                                <h3 className="text-4xl lg:text-5xl font-bold tracking-tight mb-6" style={{ color: 'var(--nm-text)' }}>{feature.title}</h3>
                                <div className="text-xl leading-relaxed font-medium opacity-70" style={{ color: 'var(--nm-text)' }}>{feature.description}</div>
                            </div>
                        </motion.div>
                    ))}
                    <div aria-hidden="true" className="h-[clamp(1.5rem,4vh,3rem)]" />
                </div>

                {/* Right Column - Sticky Visual */}
                <div
                    className="w-[50%] xl:w-[45%] h-screen sticky flex items-center justify-center"
                    style={{ top: `${desktopStickyTopOffset}px` }}
                >
                    <motion.div
                        className="w-full aspect-square relative"
                        animate={{ y: desktopVisualOffset }}
                        transition={{ duration: 0.4, ease: "easeOut" }}
                        style={{
                            borderRadius: '3rem',
                            background: 'var(--nm-base)',
                            boxShadow: '10px 10px 32px var(--nm-shadow-dark), -10px -10px 32px var(--nm-shadow-light)',
                            border: '1.5px solid rgba(255,255,255,0.45)'
                        }}>
                        <div className="absolute inset-3 nm-inset overflow-hidden" style={{ borderRadius: '2.6rem' }}>
                            <AnimatePresence mode="wait">
                                <motion.div
                                    key={activeIndex}
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.95 }}
                                    transition={{ duration: 0.4, ease: "easeOut" }}
                                    className="absolute inset-0"
                                >
                                    {FEATURES[activeIndex] && React.createElement(FEATURES[activeIndex].visual)}
                                </motion.div>
                            </AnimatePresence>
                        </div>
                    </motion.div>
                </div>
            </div>
        </div>
    );
}
