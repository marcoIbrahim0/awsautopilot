'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

const TYPE_SPEED_MS = 90;
const PAUSE_AFTER_WORD_MS = 1200;
const DELETE_SPEED_MS = 60;
const START_DELAY_MS = 800;

export interface HeroTypewriterProps {
  /** Static text before the cycling word (e.g. "Secure AWS ") */
  prefix: string;
  /** Words to cycle through for the last word only (e.g. ["quickly.", "securely."]) */
  words: string[];
  className?: string;
}

export function HeroTypewriter({ prefix, words, className }: HeroTypewriterProps) {
  const [chars, setChars] = useState<React.ReactNode[]>([]);
  const wordIndexRef = useRef(0);
  const keyRef = useRef(0);
  const slotRef = useRef<HTMLSpanElement>(null);
  const startedRef = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || words.length === 0) return;

    const makeVisible = () => {
      const el = slotRef.current;
      if (!el) return;
      const last = el.querySelector('.typewriter-hero-char:last-child');
      if (last) last.classList.add('visible');
    };

    const runCycle = () => {
      const word = words[wordIndexRef.current % words.length];
      wordIndexRef.current = (wordIndexRef.current + 1) % words.length;

      let i = 0;
      const typeNext = () => {
        if (i >= word.length) {
          setTimeout(() => {
            let j = word.length;
            const deleteNext = () => {
              if (j <= 0) {
                setChars([]);
                setTimeout(runCycle, 400);
                return;
              }
              setChars((prev) => prev.slice(0, -1));
              j--;
              setTimeout(deleteNext, DELETE_SPEED_MS);
            };
            deleteNext();
          }, PAUSE_AFTER_WORD_MS);
          return;
        }
        const ch = word[i];
        keyRef.current += 1;
        setChars((prev) => [
          ...prev,
          <span key={keyRef.current} className="typewriter-hero-char">
            {ch}
          </span>,
        ]);
        i++;
        setTimeout(typeNext, TYPE_SPEED_MS);
      };

      typeNext();
    };

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting) return;
        if (startedRef.current) return;
        startedRef.current = true;
        observer.disconnect();
        setTimeout(runCycle, START_DELAY_MS);
      },
      { threshold: 0.2 }
    );
    observer.observe(containerRef.current);

    return () => observer.disconnect();
  }, [words]);

  useEffect(() => {
    if (chars.length === 0) return;
    const id = requestAnimationFrame(() => {
      const el = slotRef.current;
      if (!el) return;
      const last = el.querySelector('.typewriter-hero-char:last-child');
      if (last) last.classList.add('visible');
    });
    return () => cancelAnimationFrame(id);
  }, [chars]);

  return (
    <div
      ref={containerRef}
      className={cn('typewriter-hero text-white', className)}
      id="hero-typewriter"
      aria-live="polite"
    >
      <span className="typewriter-hero-prefix">{prefix}</span>
      <span ref={slotRef} className="typewriter-hero-last-word">
        {chars}
      </span>
      <span className="typewriter-hero-cursor" aria-hidden />
    </div>
  );
}
