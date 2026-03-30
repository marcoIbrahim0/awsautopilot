"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "motion/react";

interface GlobalScrollTimelineProps {
    children: React.ReactNode;
}

export function GlobalScrollTimeline({ children }: GlobalScrollTimelineProps) {
    const containerRef = useRef<HTMLDivElement>(null);

    const { scrollYProgress } = useScroll({
        target: containerRef,
        offset: ["start start", "end end"]
    });

    // Hide the initial stroke dot until scrolling actually begins
    const pathOpacity = useTransform(scrollYProgress, [0, 0.05], [0, 1]);

    // A graceful, sweeping Comet-themed path
    // The line orbits the content, entering via long, smooth bezier curves
    // wrapping around the outer edges and avoiding the heavy central text blocks.
    const cometSweepPath = `
      M -50 -10
      C 0 -10, 22 10, 22 55
      C 22 100, -20 100, -50 110

      M -50 90
      C 20 90, 82 100, 82 130
      C 82 165, 120 160, 150 170

      M 150 150
      C 100 150, 18 170, 18 205
      C 18 240, 100 240, 150 250

      M 150 240
      C 110 240, 76 255, 76 280
      C 76 300, 120 310, 150 320

      M -50 380
      C 10 380, 80 430, 80 480
      C 80 520, 20 540, -50 550

      M 150 580
      C 90 580, 20 630, 20 680
      C 20 720, 80 740, 150 750

      M -50 780
      C 10 780, 80 830, 80 880
      C 80 920, 20 940, -50 950
    `;

    return (
        <div ref={containerRef} className="relative w-full">
            {/* The Global Snaking Background Line */}
            <div className="absolute inset-0 w-full h-full z-0 pointer-events-none overflow-hidden">
                <svg
                    className="w-full h-full overflow-visible"
                    viewBox="0 0 100 1000"
                    preserveAspectRatio="none"
                >
                    {/* Sweeping Comet Line */}
                    <motion.path
                        d={cometSweepPath}
                        stroke="var(--accent)"
                        strokeWidth="3"
                        vectorEffect="non-scaling-stroke"
                        fill="none"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        style={{ pathLength: scrollYProgress, opacity: pathOpacity }}
                    />
                </svg>
            </div>

            {/* All Section Content sits on top of the line */}
            <div className="relative z-10 w-full h-full">
                {children}
            </div>
        </div>
    );
}
