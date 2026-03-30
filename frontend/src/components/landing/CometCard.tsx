'use client';

import { cn } from '@/lib/utils';

interface CometCardProps {
  children: React.ReactNode;
  className?: string;
  image?: string;
}

export function CometCard({ children, className, image }: CometCardProps) {
  return (
    <div
      className={cn(
        'group relative overflow-hidden rounded-xl bg-gradient-to-br from-white/[0.05] to-transparent ring-1 ring-white/5 shadow-lg backdrop-blur-md',
        'before:absolute before:-inset-[1px] before:rounded-xl before:opacity-0 before:transition-opacity before:duration-300',
        'before:bg-[linear-gradient(90deg,transparent,rgba(10,113,255,0.4),transparent)] before:bg-[length:200%_100%]',
        'hover:before:opacity-100 hover:before:animate-comet-shine',
        className
      )}
    >
      {image && (
        <div className="relative h-40 w-full overflow-hidden bg-surface">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={image}
            alt=""
            className="h-full w-full object-cover object-center transition-transform duration-300 group-hover:scale-105"
          />
        </div>
      )}
      <div className="relative z-10 p-5">{children}</div>
    </div>
  );
}
