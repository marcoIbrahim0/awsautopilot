'use client';

import { cn } from '@/lib/utils';

interface BrowserWindowMockProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export function BrowserWindowMock({
  title = 'Baseline Report',
  children,
  className,
}: BrowserWindowMockProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-surface-alt overflow-hidden shadow-card',
        className
      )}
    >
      <div className="flex items-center gap-2 border-b border-border bg-surface px-3 py-2">
        <div className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        </div>
        <span className="text-muted text-xs flex-1 text-center truncate">{title}</span>
      </div>
      <div className="p-4 min-h-[200px] text-sm">{children}</div>
    </div>
  );
}
