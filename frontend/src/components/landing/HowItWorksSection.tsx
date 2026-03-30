'use client';

import { TracingBeam } from './TracingBeam';
import { cn } from '@/lib/utils';

const STEPS = [
  { title: 'Sign up', description: 'Create an account in minutes.' },
  {
    title: 'Connect read-only AWS',
    description: 'CloudFormation + ExternalId. We assume a role with read-only permissions.',
  },
  {
    title: 'We run the scan',
    description: 'We analyze your posture and prioritize what matters.',
  },
  {
    title: 'Get your baseline report in 48 hours',
    description: 'Delivered by email. One-off report.',
  },
];

const SIDE_PANEL_ITEMS = [
  'AWS account access to deploy a CloudFormation stack',
  'ExternalId (provided during onboarding)',
  'No WriteRole required for the baseline',
];

export function HowItWorksSection() {
  return (
    <section className="relative px-4 py-20 sm:px-6" id="how-it-works">
      <div className="mx-auto max-w-6xl">
        <div className="text-center">
          <h2 className="text-3xl font-bold tracking-tight text-text sm:text-4xl">
            How the free baseline works
          </h2>
          <p className="mt-3 text-muted text-lg">
            Read-only connection → analysis → report in 48 hours.
          </p>
        </div>

        <div className="mt-14 grid gap-10 lg:grid-cols-[1fr_280px]">
          <div className="rounded-xl border border-border bg-surface-alt p-6 sm:p-8">
            <TracingBeam steps={STEPS} />
          </div>
          <div
            className={cn(
              'order-first lg:order-last',
              'rounded-xl border border-border bg-surface-alt p-5',
              'h-fit lg:sticky lg:top-24'
            )}
          >
            <h3 className="font-semibold text-text text-sm">What you&apos;ll need</h3>
            <ul className="mt-3 space-y-2 text-muted text-sm">
              {SIDE_PANEL_ITEMS.map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="text-accent">•</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
