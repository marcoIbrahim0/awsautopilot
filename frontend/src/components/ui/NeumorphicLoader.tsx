'use client';

import React from 'react';
import { motion } from 'motion/react';

export function NeumorphicLoader({ text = "Loading..." }: { text?: string }) {
    return (
        <div className="flex flex-col items-center justify-center space-y-6">
            <div
                className="w-16 h-16 rounded-full nm-inset relative flex items-center justify-center"
            >
                <motion.div
                    className="w-10 h-10 rounded-full nm-raised border-[1px] border-white/20"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                >
                    <div className="absolute top-1 right-1 w-2.5 h-2.5 bg-[#4a84e8] rounded-full shadow-[0_0_8px_rgba(74,132,232,0.8)]" />
                </motion.div>
            </div>
            <p className="text-sm font-medium tracking-wide" style={{ color: 'var(--nm-text-muted)' }}>
                {text}
            </p>
        </div>
    );
}
