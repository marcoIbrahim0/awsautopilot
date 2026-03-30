'use client';

import { motion } from 'motion/react';
import { DynamicIslandPill } from './DynamicIslandPill';
import { GlowingEffect } from './GlowingEffect';
import { EncryptedText } from './EncryptedText';
import { TextHoverEffect } from './TextHoverEffect';
import { StickyScrollReveal } from './StickyScrollReveal';

const BULLETS = [
  'Prioritized work your engineers can actually do',
  'Guardrails that prevent repeat issues',
  'Evidence and narratives for SOC 2',
];

export function DifferentiatorSection() {
  return (
    <section className="relative px-4 py-20 sm:px-6" id="outcomes">
      <div className="mx-auto max-w-6xl min-h-[60vh]">
        <StickyScrollReveal>
          <div>
            <div className="text-center">
              <h2 className="text-3xl font-bold tracking-tight text-text sm:text-4xl">
                Not more findings—outcomes
              </h2>
              <div className="mt-4 flex justify-center">
                <DynamicIslandPill
                  steps={[
                    { label: 'Baseline', active: true },
                    { label: 'Fixes', active: true },
                    { label: 'Evidence', active: true },
                  ]}
                />
              </div>
              <p className="mt-6 text-muted text-lg">
                <EncryptedText duration={1200}>Fixes shipped, guardrails in place, and proof ready for auditors.</EncryptedText>
              </p>
              <p className="mt-2 text-muted text-sm">
                <TextHoverEffect as="span">Secure AWS quickly, stay secure with minimal weekly effort.</TextHoverEffect>
              </p>
            </div>

            <div className="mt-12 flex justify-center">
              <GlowingEffect className="max-w-2xl">
                <ul className="space-y-3 text-muted text-sm">
                  {BULLETS.map((bullet, i) => (
                    <motion.li
                      key={bullet}
                      className="flex gap-2"
                      initial={{ opacity: 0, x: -8 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.3, delay: i * 0.05 }}
                    >
                      <span className="text-accent font-medium">•</span>
                      {bullet}
                    </motion.li>
                  ))}
                </ul>
              </GlowingEffect>
            </div>
          </div>
        </StickyScrollReveal>
      </div>
    </section>
  );
}
