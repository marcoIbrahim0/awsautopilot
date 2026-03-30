'use client';

import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';

const CHARS = '01ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';

function scramble(str: string, progress: number): string {
  return str
    .split('')
    .map((char, i) => {
      if (char === ' ') return ' ';
      const threshold = 1 - (i / str.length) * (1 - progress);
      return Math.random() < threshold ? CHARS[Math.floor(Math.random() * CHARS.length)] : char;
    })
    .join('');
}

interface EncryptedTextProps {
  children: React.ReactNode;
  className?: string;
  duration?: number;
  decryptionSpeed?: number;
}

export function EncryptedText({
  children,
  className,
  duration = 1000,
  decryptionSpeed = 30,
}: EncryptedTextProps) {
  const text = typeof children === 'string' ? children : String(children ?? '');
  const [display, setDisplay] = useState(text);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    if (revealed) return;
    let start: number;
    let raf: number;
    const animate = (timestamp: number) => {
      if (!start) start = timestamp;
      const elapsed = timestamp - start;
      const progress = Math.min(elapsed / duration, 1);
      setDisplay(scramble(text, progress));
      if (progress < 1) {
        raf = requestAnimationFrame(animate);
      } else {
        setDisplay(text);
        setRevealed(true);
      }
    };
    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [text, duration, revealed]);

  return <span className={cn('font-mono', className)}>{display}</span>;
}
