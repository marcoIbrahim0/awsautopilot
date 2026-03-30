'use client';

import React from 'react';
import Link from 'next/link';
import { NoiseBackground } from '@/components/ui/NoiseBackground';

interface PrimaryCTANeumorphicProps {
    href: string;
    text?: string;
    className?: string;
}

export function PrimaryCTANeumorphic({
    href,
    text = "Book a 20-minute walkthrough",
    className = ""
}: PrimaryCTANeumorphicProps) {
    return (
        <div className={`group inline-flex shrink-0 transition-all duration-150 ease-out hover:-translate-y-[1px] active:translate-y-[1px] ${className}`}>
            <NoiseBackground
                containerClassName="inline-flex rounded-[2rem] p-[1px] nm-raised transition-all duration-150 group-hover:shadow-[7px_7px_18px_var(--nm-shadow-dark),-7px_-7px_18px_var(--nm-shadow-light)] group-active:shadow-[inset_3px_3px_8px_var(--nm-shadow-dark),inset_-3px_-3px_8px_var(--nm-shadow-light)]"
                style={{ borderRadius: '2rem' }}
                gradientColors={['rgb(62, 140, 255)', 'rgb(42, 114, 235)', 'rgb(35, 98, 210)']}
                noiseIntensity={0.36}
                speed={0.04}
            >
                <NoiseBackground
                    containerClassName="inline-flex rounded-[1.9375rem] p-[3px]"
                    style={{ borderRadius: '1.9375rem' }}
                    gradientColors={['rgb(90, 170, 255)', 'rgb(62, 140, 255)', 'rgb(42, 114, 235)']}
                    noiseIntensity={0.42}
                    speed={0.04}
                >
                    <Link
                        href={href}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex rounded-[1.75rem] border-0 px-6 py-2.5 text-sm font-semibold outline-none backdrop-blur-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#dde6f0] transition-colors hover:text-accent"
                        style={{
                            color: 'var(--nm-text)',
                            background: 'var(--nm-base)',
                            boxShadow: 'inset 3px 3px 8px var(--nm-shadow-dark), inset -3px -3px 8px var(--nm-shadow-light)',
                            borderRadius: '1.75rem'
                        }}
                    >
                        {text}
                    </Link>
                </NoiseBackground>
            </NoiseBackground>
        </div>
    );
}
