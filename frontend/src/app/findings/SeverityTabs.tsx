'use client';

interface SeverityTabsProps {
  selected: string | null;
  onChange: (severity: string | null) => void;
  counts?: Record<string, number>;
}

const tabs = [
  { value: null, label: 'All' },
  { value: 'CRITICAL', label: 'Critical' },
  { value: 'HIGH', label: 'High' },
  { value: 'MEDIUM', label: 'Medium' },
  { value: 'LOW', label: 'Low' },
];

export function SeverityTabs({ selected, onChange, counts }: SeverityTabsProps) {
  return (
    <div className="flex items-center gap-1 p-1 nm-neu-pressed rounded-2xl overflow-x-auto no-scrollbar max-w-full">
      {tabs.map((tab) => {
        const isSelected = tab.value === selected;
        const count = tab.value ? counts?.[tab.value] : undefined;

        return (
          <button
            key={tab.label}
            onClick={() => onChange(tab.value)}
            className={`
              px-3 py-1.5 text-sm font-semibold rounded-xl shrink-0
              transition-all duration-300 tracking-tight
              ${isSelected
                ? 'nm-neu-sm text-[#4D9BFF]'
                : 'text-muted hover:text-text hover:nm-neu-sm'
              }
            `}
          >
            {tab.label}
            {count !== undefined && count > 0 && (
              <span
                className={`ml-1.5 text-xs font-mono opacity-70 ${
                  isSelected ? 'text-[#4D9BFF]' : 'text-muted'
                }`}
              >
                ({count})
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
