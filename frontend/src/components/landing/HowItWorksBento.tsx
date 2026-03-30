'use client';

import Image from 'next/image';
import { cn } from '@/lib/utils';

type BentoTileProps = {
  title: string;
  description: string;
  header?: React.ReactNode;
  className?: string;
  fadedBorder?: boolean;
};

function BentoTile({ title, description, header, className, fadedBorder }: BentoTileProps) {
  return (
    <div
      className={cn(
        'relative h-full min-h-[16rem] rounded-2xl md:aspect-square',
        fadedBorder && 'p-px',
        className
      )}
    >
      {fadedBorder && (
        <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-[var(--accent)]/35 via-white/10 to-transparent" />
      )}
      <div
        className={cn(
          'relative flex h-full flex-col justify-between rounded-2xl border border-white/10 bg-[#0b1128]/85 p-6 shadow-[0_20px_60px_rgba(2,8,23,0.45)] backdrop-blur',
          fadedBorder && 'border-white/10'
        )}
      >
        {header}
        <div className="mt-4">
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <p className="mt-2 text-sm leading-relaxed text-white/70">{description}</p>
        </div>
      </div>
    </div>
  );
}

function LogoHeader() {
  return (
    <div className="relative h-20 w-full overflow-hidden rounded-xl border border-white/10 bg-[#0a1024]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(56,92,176,0.35),transparent_55%),radial-gradient(circle_at_80%_0%,rgba(14,165,233,0.25),transparent_60%)]" />
      <div className="relative flex h-full items-center justify-center">
        <Image
          src="/logo/ocypheris-logo.svg"
          alt="Ocypheris"
          width={220}
          height={70}
          className="h-8 w-auto opacity-90"
          loading="lazy"
        />
      </div>
    </div>
  );
}

function CardStackHeader() {
  return (
    <div className="relative h-24 w-full">
      <div className="absolute left-2 top-3 h-20 w-32 rounded-xl border border-white/15 bg-[#0a1024] shadow-[0_12px_40px_rgba(2,8,23,0.6)]" />
      <div className="absolute left-6 top-1 h-20 w-32 -rotate-3 rounded-xl border border-white/20 bg-[#0f1733] shadow-[0_16px_46px_rgba(2,8,23,0.65)]" />
      <div className="absolute left-10 top-0 h-20 w-32 rotate-3 rounded-xl border border-white/25 bg-[#121d3f] shadow-[0_18px_55px_rgba(2,8,23,0.7)]">
        <div className="flex h-full items-center justify-center">
          <Image
            src="/logo/ocypheris-logo.svg"
            alt="Ocypheris"
            width={160}
            height={50}
            className="h-6 w-auto opacity-90"
            loading="lazy"
          />
        </div>
      </div>
    </div>
  );
}

function GlobeHeader() {
  const dots = [
    [70, 60],
    [90, 52],
    [110, 58],
    [122, 80],
    [96, 90],
    [84, 98],
    [120, 100],
    [76, 78],
    [130, 70],
    [112, 118],
    [86, 118],
  ];

  return (
    <div className="relative h-28 w-full overflow-hidden rounded-xl border border-white/10 bg-[#0a1024]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(56,92,176,0.3),transparent_60%),radial-gradient(circle_at_80%_0%,rgba(14,165,233,0.25),transparent_65%)]" />
      <div className="relative flex h-full items-center justify-center">
        <div className="relative h-24 w-24">
          <svg viewBox="0 0 200 200" className="h-full w-full">
            <circle cx="100" cy="100" r="72" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="2" />
            <ellipse cx="100" cy="100" rx="60" ry="24" fill="none" stroke="rgba(125,211,252,0.25)" strokeWidth="1" />
            <ellipse cx="100" cy="100" rx="60" ry="40" fill="none" stroke="rgba(125,211,252,0.2)" strokeWidth="1" />
            <ellipse cx="100" cy="100" rx="60" ry="56" fill="none" stroke="rgba(125,211,252,0.15)" strokeWidth="1" />
            <g className="origin-center animate-[spin_20s_linear_infinite]">
              {dots.map((dot, i) => (
                <circle key={`dot-${i}`} cx={dot[0]} cy={dot[1]} r="2.2" fill="rgba(125,211,252,0.9)" />
              ))}
            </g>
          </svg>
          <div className="absolute inset-0 rounded-full shadow-[0_0_30px_rgba(56,189,248,0.35)]" />
        </div>
      </div>
    </div>
  );
}

export function HowItWorksBento() {
  return (
    <div className="mt-10 grid grid-cols-1 gap-2 md:grid-cols-2 md:gap-2">
      <BentoTile
        title="Connect"
        description="Connect your AWS account with a read-only role. No long-lived keys—we use STS AssumeRole and External ID."
        header={<LogoHeader />}
        fadedBorder
      />
      <BentoTile
        title="Fix"
        description="Approve safe direct fixes or merge PR bundles. You stay in control; we never change anything without approval."
        header={<CardStackHeader />}
      />
      <BentoTile
        title="Prove"
        description="Export evidence packs and exception governance for SOC 2 and ISO readiness."
        header={<LogoHeader />}
      />
      <BentoTile
        title="See"
        description="Security Hub and GuardDuty findings become prioritized actions. Top risks first, noise reduced."
        header={<GlobeHeader />}
      />
    </div>
  );
}
