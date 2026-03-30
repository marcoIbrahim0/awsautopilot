'use client';

import { AnimatePresence, motion } from 'motion/react';
import { Search } from 'lucide-react';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { cn } from '@/lib/utils';

interface PlaceholdersAndVanishInputProps {
  placeholders: string[];
  value: string;
  onChange: (value: string) => void;
  onSubmit?: (value: string) => void;
  className?: string;
  inputClassName?: string;
  buttonClassName?: string;
}

export function PlaceholdersAndVanishInput({
  placeholders,
  value,
  onChange,
  onSubmit,
  className,
  inputClassName,
  buttonClassName,
}: PlaceholdersAndVanishInputProps) {
  const [placeholderIndex, setPlaceholderIndex] = useState(0);

  const safePlaceholders = useMemo(
    () => (placeholders.length > 0 ? placeholders : ['Search...']),
    [placeholders]
  );

  useEffect(() => {
    const interval = window.setInterval(() => {
      setPlaceholderIndex((current) => (current + 1) % safePlaceholders.length);
    }, 2600);

    return () => window.clearInterval(interval);
  }, [safePlaceholders]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit?.(value.trim());
  };

  return (
    <form onSubmit={handleSubmit} className={cn('relative w-full max-w-xl', className)}>
      <div className="relative flex h-11 w-full items-center rounded-2xl border-none bg-transparent nm-neu-pressed px-3 transition-colors focus-within:ring-2 focus-within:ring-accent/50">
        <Search className="h-4 w-4 shrink-0 text-muted" />

        <div className="relative ml-2 flex-1">
          {!value && (
            <AnimatePresence mode="wait">
              <motion.span
                key={safePlaceholders[placeholderIndex]}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.2 }}
                className="pointer-events-none absolute inset-y-0 flex items-center text-sm text-muted"
              >
                {safePlaceholders[placeholderIndex]}
              </motion.span>
            </AnimatePresence>
          )}

          <input
            type="text"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            className={cn(
              'h-10 w-full bg-transparent pr-16 text-sm text-text outline-none',
              inputClassName
            )}
            aria-label="Search"
          />
        </div>

        <button
          type="submit"
          className={cn(
            'inline-flex h-8 items-center justify-center rounded-lg px-3 text-xs font-medium text-muted transition-colors hover:bg-accent/10 hover:text-text',
            buttonClassName
          )}
        >
          Search
        </button>
      </div>
    </form>
  );
}
