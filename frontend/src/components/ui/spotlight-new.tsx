"use client";

import React from "react";
import { motion } from "motion/react";

type SpotlightProps = {
  gradientFirst?: string;
  gradientSecond?: string;
  gradientThird?: string;
  translateY?: number;
  width?: number;
  height?: number;
  smallWidth?: number;
  duration?: number;
  xOffset?: number;
};

/**
 * Stock Aceternity UI Spotlight New.
 * Usage: wrapper div with bg-black/[0.96] etc, then <Spotlight />, then content with relative z-10.
 */
export const Spotlight = ({
  gradientFirst = "radial-gradient(68.54% 68.72% at 55.02% 31.46%, hsla(210, 100%, 85%, .08) 0, hsla(210, 100%, 55%, .02) 50%, hsla(210, 100%, 45%, 0) 80%)",
  gradientSecond = "radial-gradient(50% 50% at 50% 50%, hsla(210, 100%, 85%, .06) 0, hsla(210, 100%, 55%, .02) 80%, transparent 100%)",
  gradientThird = "radial-gradient(50% 50% at 50% 50%, hsla(210, 100%, 85%, .04) 0, hsla(210, 100%, 45%, .02) 80%, transparent 100%)",
  translateY = -350,
  width = 560,
  height = 1380,
  smallWidth = 240,
  duration = 7,
  xOffset = 100,
}: SpotlightProps = {}) => {
  return (
    <>
      <motion.div
        className="absolute opacity-90"
        style={{
          width: `${width}px`,
          height: `${height}px`,
          left: "50%",
          top: "50%",
          transform: `translate(-50%, calc(-50% + ${translateY}px))`,
          background: gradientFirst,
        }}
        animate={{
          x: [-xOffset, xOffset, -xOffset],
        }}
        transition={{
          duration,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      <motion.div
        className="absolute opacity-80"
        style={{
          width: `${width * 0.8}px`,
          height: `${height * 0.6}px`,
          left: "30%",
          top: "40%",
          background: gradientSecond,
        }}
        animate={{
          x: [xOffset, -xOffset, xOffset],
        }}
        transition={{
          duration: duration + 1,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      <motion.div
        className="absolute opacity-70"
        style={{
          width: `${width * 0.6}px`,
          height: `${height * 0.5}px`,
          right: "20%",
          top: "50%",
          background: gradientThird,
        }}
        animate={{
          x: [-xOffset, xOffset, -xOffset],
        }}
        transition={{
          duration: duration + 2,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
    </>
  );
};
