'use client';

import { SOURCE_FILTER_VALUES } from '@/lib/source';

interface SourceTabsProps {
  selected: string;
  onChange: (source: string) => void;
}

export function SourceTabs({ selected, onChange }: SourceTabsProps) {
  return (
    <div className="flex items-center gap-1 p-1 nm-neu-pressed rounded-2xl overflow-x-auto no-scrollbar max-w-full">
      {SOURCE_FILTER_VALUES.map((tab) => {
        const isSelected = tab.value === selected;
        return (
          <button
            key={tab.value || 'all'}
            onClick={() => onChange(tab.value)}
            className={`
              px-3 py-1.5 text-sm font-semibold rounded-xl shrink-0
              transition-all duration-300 tracking-tight
              ${isSelected
                ? 'nm-neu-sm text-accent'
                : 'text-muted hover:text-text hover:nm-neu-sm'
              }
            `}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
