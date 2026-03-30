"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import Image from "next/image";

import { cn } from "@/lib/utils";

type ShieldStackCounterProps = {
  total?: number;
  size?: number;
  label?: string;
  detail?: string;
  showMeta?: boolean;
  className?: string;
  accentCount?: number;
  accentColor?: string;
  baseColor?: string;
};

export function ShieldStackCounter({
  total = 7,
  size = 252,
  label = "Playbooks",
  detail = "",
  showMeta = false,
  className,
}: ShieldStackCounterProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [count, setCount] = useState(0);

  const clampedTotal = Math.max(1, total);
  const shieldSize = Math.max(40, Math.round(size * 0.32));
  const stackOffset = Math.max(14, Math.round(size * 0.085));
  const curveAmount = Math.max(10, Math.round(size * 0.055));
  const stackCenter = 0.42;

  const ariaLabel = useMemo(() => {
    const detailText = detail ? ` ${detail}.` : "";
    return `${label}: ${clampedTotal}.${detailText}`;
  }, [clampedTotal, detail, label]);

  useEffect(() => {
    const node = rootRef.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.35 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!isVisible) return;

    let current = 0;
    const interval = setInterval(() => {
      current += 1;
      setCount(current);
      if (current >= clampedTotal) {
        clearInterval(interval);
      }
    }, 350);

    return () => clearInterval(interval);
  }, [clampedTotal, isVisible]);

  return (
    <figure
      ref={rootRef}
      className={cn("flex flex-col items-center text-center", className)}
      style={{ width: Math.max(152, size + 32) }}
      aria-label={ariaLabel}
    >
      <div
        className="relative"
        style={{ width: size, height: Math.round(size * 0.95) }}
      >
        <div className="absolute left-4 top-1/2 z-20 -translate-y-1/2">
          <AnimatePresence mode="wait">
            <motion.span
              key={count}
              initial={{ scale: 0.65, y: 12, rotate: -8, opacity: 0 }}
              animate={{ scale: 1.12, y: 0, rotate: 0, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: "spring", stiffness: 360, damping: 18 }}
              className="text-5xl font-semibold tracking-tight text-white"
            >
              {count}
            </motion.span>
          </AnimatePresence>
        </div>

        <div className="absolute inset-0 z-10">
          {Array.from({ length: clampedTotal }).map((_, index) => {
            const isActive = index < count;
            const centerIndex = (clampedTotal - 1) / 2;
            const t = clampedTotal > 1 ? index / (clampedTotal - 1) : 0;
            const baseX = (index - centerIndex) * Math.max(8, Math.round(size * 0.035));
            const curveX = Math.sin(t * Math.PI) * curveAmount - curveAmount / 2;
            const x = baseX + curveX;
            const y = index * stackOffset;
            const wobble = Math.cos(t * Math.PI) * Math.max(4, Math.round(size * 0.02));
            const rotate = (index - centerIndex) * 2.5;
            return (
              <motion.div
                key={index}
                className="absolute top-1/2"
                style={{ left: `${stackCenter * 100}%`, transform: "translate(-50%, -50%)" }}
                initial={{ opacity: 0, y: 28, scale: 1.3, rotate: rotate - 8 }}
                animate={
                  isActive
                    ? { opacity: 1, y: -y + wobble, x, scale: 1, rotate }
                    : { opacity: 0, y: 28, scale: 1.1 }
                }
                transition={{
                  type: "spring",
                  stiffness: 520,
                  damping: 18,
                }}
              >
                <Image
                  src="/images/small-shield2.png"
                  alt=""
                  width={shieldSize}
                  height={shieldSize}
                  priority={false}
                  className="select-none object-contain"
                  style={{
                    opacity: isActive ? 1 : 0.4,
                  }}
                />
              </motion.div>
            );
          })}
        </div>
      </div>

      {showMeta ? (
        <div className="mt-2 text-xs font-semibold text-white/90">{label}</div>
      ) : null}
      {showMeta && detail ? (
        <div className="mt-0.5 text-xs text-white/60">{detail}</div>
      ) : null}
    </figure>
  );
}
