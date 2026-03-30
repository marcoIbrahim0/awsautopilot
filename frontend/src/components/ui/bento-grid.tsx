'use client';

import { cn } from '@/lib/utils';

type BentoGridProps = {
  className?: string;
  children: React.ReactNode;
};

type BentoGridItemProps = {
  className?: string;
  title: string;
  description: string;
  header?: React.ReactNode;
  icon?: React.ReactNode;
};

export function BentoGrid({ className, children }: BentoGridProps) {
  return (
    <div
      className={cn(
        'grid auto-rows-[14rem] grid-cols-1 gap-4 md:auto-rows-[18rem] md:grid-cols-3',
        className
      )}
    >
      {children}
    </div>
  );
}

export function BentoGridItem({
  className,
  title,
  description,
  header,
  icon,
}: BentoGridItemProps) {
  return (
    <div
      className={cn(
        'group/bento row-span-1 flex flex-col justify-between space-y-4 rounded-2xl border border-white/10 bg-[#0b1128]/80 p-5 shadow-[0_20px_60px_rgba(2,8,23,0.45)] backdrop-blur transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_25px_70px_rgba(2,8,23,0.6)]',
        className
      )}
    >
      {header}
      <div className="transition duration-200 group-hover/bento:translate-x-2">
        {icon}
        <div className="mt-2 text-base font-semibold text-white">{title}</div>
        <div className="mt-1 text-sm leading-relaxed text-white/70">{description}</div>
      </div>
    </div>
  );
}
