'use client';

import { useState, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'motion/react';

/**
 * Aceternity-style animated tabs.
 * @see https://ui.aceternity.com/components/tabs
 */
export interface Tab {
  title: string;
  value: string;
  content: ReactNode;
}

export interface TabsProps {
  tabs: Tab[];
  containerClassName?: string;
  activeTabClassName?: string;
  tabClassName?: string;
  contentClassName?: string;
}

export function Tabs({
  tabs,
  containerClassName = '',
  activeTabClassName = '',
  tabClassName = '',
  contentClassName = '',
}: TabsProps) {
  const [active, setActive] = useState(tabs[0]?.value ?? '');

  const activeTab = tabs.find((t) => t.value === active) ?? tabs[0];

  return (
    <div className={containerClassName}>
      <div className="flex flex-wrap gap-1 rounded-xl border border-border bg-dropdown-bg p-1">
        {tabs.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => setActive(tab.value)}
            className={`relative rounded-xl px-3 py-2 text-sm font-medium transition-colors ${tabClassName} ${
              active === tab.value
                ? `text-text ${activeTabClassName}`
                : 'text-muted hover:text-text'
            }`}
          >
            {active === tab.value && (
              <motion.span
                layoutId="tabs-active"
                className={`absolute inset-0 rounded-xl bg-accent/15 ${activeTabClassName}`}
                transition={{ type: 'spring', bounce: 0.2, duration: 0.4 }}
              />
            )}
            <span className="relative z-10">{tab.title}</span>
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        {activeTab && (
          <motion.div
            key={activeTab.value}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
            className={`mt-3 ${contentClassName}`}
          >
            {activeTab.content}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
