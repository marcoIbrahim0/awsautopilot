'use client';

interface StatusTabsProps {
  selected: string | null;
  onChange: (status: string | null) => void;
}

const tabs: { value: string | null; label: string }[] = [
  { value: null, label: 'All' },
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'resolved', label: 'Resolved' },
];

export function StatusTabs({ selected, onChange }: StatusTabsProps) {
  return (
    <div className="flex items-center gap-1 p-1 bg-surface rounded-xl border border-border">
      {tabs.map((tab) => {
        const isSelected = tab.value === selected;
        return (
          <button
            key={tab.label}
            type="button"
            onClick={() => onChange(tab.value)}
            className={`
              px-4 py-2 text-sm font-medium rounded-xl
              transition-all duration-150
              ${isSelected
                ? 'bg-accent text-bg shadow-sm'
                : 'text-muted hover:text-text hover:bg-bg'
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
