'use client';

import React from 'react';
import { motion } from 'motion/react';
import Image from 'next/image';

const INTEGRATIONS = [
    { name: 'AWS Security Hub', icon: '/images/integrations/securityhub.svg' },
    { name: 'Amazon EventBridge', icon: '/images/integrations/eventbridge.svg' },
    { name: 'AWS IAM', icon: '/images/integrations/iam.svg' },
    { name: 'Terraform', icon: '/images/integrations/terraform.svg' },
    { name: 'Slack', icon: '/images/integrations/slack.svg' },
    { name: 'GitHub', icon: '/images/integrations/github.svg' },
    { name: 'Jira', icon: '/images/integrations/jira.svg' },
];

export const IntegrationsMarquee = () => {
    // Duplicate the array to create a seamless loop
    const doubledIntegrations = [...INTEGRATIONS, ...INTEGRATIONS];

    return (
        <section className="relative z-10 w-full overflow-hidden border-y border-white/5 bg-transparent py-10 sm:py-14">
            <div className="mx-auto max-w-7xl px-6 lg:px-8 flex flex-col items-center">
                <p className="text-center text-sm font-semibold uppercase tracking-wider text-white/50 mb-8">
                    Seamlessly plugs into your existing security & engineering stack
                </p>

                {/* Marquee Container */}
                <div className="relative flex w-full overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]">
                    <motion.div
                        className="flex shrink-0 items-center justify-center gap-12 sm:gap-20"
                        animate={{
                            x: ['0%', '-50%'],
                        }}
                        transition={{
                            duration: 35,
                            ease: 'linear',
                            repeat: Infinity,
                        }}
                    >
                        {doubledIntegrations.map((integration, index) => (
                            <div
                                key={`${integration.name}-${index}`}
                                className="flex items-center gap-3 opacity-60 grayscale transition-all hover:opacity-100 hover:grayscale-0"
                            >
                                <div className="relative h-8 w-8 sm:h-10 sm:w-10">
                                    {/* Using an img tag to handle fallback if the SVG files aren't physically present yet, 
                                        we will rely on their future creation or adjust manually if the user has specific assets. 
                                        For now, we'll build the structure. */}
                                    <div className="h-full w-full rounded-md bg-white/10 border border-white/20 flex items-center justify-center text-xs text-white/40">
                                        Logo
                                    </div>
                                </div>
                                <span className="text-lg font-medium text-white/80 whitespace-nowrap">
                                    {integration.name}
                                </span>
                            </div>
                        ))}
                    </motion.div>
                </div>
            </div>
        </section>
    );
};
