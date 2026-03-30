 "use client";

import React, { useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";

type DonutSegment = { value: number; color: string };

export function DonutStat({
  size = 80,
  strokeWidth = 8,
  centerText,
  centerContent,
  label,
  detail,
  variant,
  percent,
  segments,
  showMeta = true,
}: {
  size?: number;
  strokeWidth?: number;
  centerText: string;
  centerContent?: React.ReactNode;
  label: string;
  detail: string;
  variant: "percent" | "split" | "solid";
  percent?: number;
  segments?: DonutSegment[];
  showMeta?: boolean;
}) {
  const rootRef = useRef<HTMLElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [drawProgress, setDrawProgress] = useState(0);
  const [displayNumber, setDisplayNumber] = useState<string | null>(null);

  const r = (size - strokeWidth) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;
  const topGapRatio = 0.1;
  const topGap = circumference * topGapRatio;
  const visibleArc = circumference - topGap;
  const segmentGap = circumference * 0.018;
  const darkTrackStrokeWidth = Math.max(2, strokeWidth - 3);

  const ariaLabel = `${label}: ${centerText}. ${detail}.`;

  const normalizedPercent =
    typeof percent === "number" ? Math.max(0, Math.min(100, percent)) : 0;

  const parsedCenter = useMemo(() => {
    const match = centerText.trim().match(/^(\d+)(.*)$/);
    if (!match) return null;
    return { value: Number(match[1]), suffix: match[2] ?? "" };
  }, [centerText]);

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

    const durationMs = 1000;
    const start = performance.now();

    const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

    const tick = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      const eased = easeOut(t);
      setDrawProgress(eased);

      if (parsedCenter) {
        const current = Math.round(parsedCenter.value * eased);
        setDisplayNumber(`${current}${parsedCenter.suffix}`);
      }

      if (t < 1) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  }, [isVisible, parsedCenter]);

  const renderArc = () => {
    if (variant === "solid") {
      return (
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="rgba(56, 189, 248, 0.92)"
          strokeWidth={strokeWidth}
          strokeLinecap="butt"
          strokeDasharray={`${visibleArc * drawProgress} ${circumference}`}
          strokeDashoffset={0}
          transform={`rotate(-90 ${cx} ${cy})`}
        />
      );
    }

    if (variant === "percent") {
      const percentArc = visibleArc * (normalizedPercent / 100) * drawProgress;
      return (
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="rgba(56, 189, 248, 0.92)"
          strokeWidth={strokeWidth}
          strokeLinecap="butt"
          strokeDasharray={`${percentArc} ${circumference}`}
          strokeDashoffset={0}
          transform={`rotate(-90 ${cx} ${cy})`}
        />
      );
    }

    const segs = (segments ?? []).filter((s) => s.value > 0);
    const total = segs.reduce((acc, s) => acc + s.value, 0);
    if (total <= 0) return null;

    const totalGap = segmentGap * segs.length;
    const drawable = Math.max(0, visibleArc - totalGap) * drawProgress;
    let cursor = 0;

      return segs.map((s, i) => {
      const segLen = (s.value / total) * drawable;
      const dashArray = `${segLen} ${circumference}`;
      const dashOffset = -cursor;
      const isDarkBlueSegment = s.color.includes("19, 58, 102");
      cursor += segLen + segmentGap;
      return (
        <circle
          key={i}
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={s.color}
          strokeWidth={isDarkBlueSegment ? darkTrackStrokeWidth : strokeWidth}
          strokeLinecap="butt"
          strokeDasharray={dashArray}
          strokeDashoffset={dashOffset}
          transform={`rotate(-90 ${cx} ${cy})`}
        />
      );
    });
  };

  return (
    <figure
      ref={rootRef}
      className="flex flex-col items-center text-center"
      style={{ width: Math.max(152, size + 32) }}
      aria-label={ariaLabel}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="block"
          aria-hidden="true"
        >
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="rgba(19, 58, 102, 0.9)"
            strokeWidth={darkTrackStrokeWidth}
            strokeDasharray={`${visibleArc} ${topGap}`}
            strokeDashoffset={0}
            transform={`rotate(-90 ${cx} ${cy})`}
          />
          {renderArc()}
        </svg>
        <div
          className={cn(
            "absolute inset-0 grid place-items-center",
            "font-semibold tracking-tight text-white",
          )}
          style={{ fontSize: Math.max(18, Math.round(size * 0.2)) }}
        >
          {centerContent ?? displayNumber ?? centerText}
        </div>
      </div>
      {showMeta ? <div className="mt-2 text-xs font-semibold text-white/90">{label}</div> : null}
      {showMeta ? <div className="mt-0.5 text-xs text-white/60">{detail}</div> : null}
    </figure>
  );
}
