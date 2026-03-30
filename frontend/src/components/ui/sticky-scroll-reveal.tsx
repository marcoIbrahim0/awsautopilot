"use client";

import React, { useRef, useState } from "react";
import { motion, useMotionValueEvent, useScroll } from "motion/react";
import { cn } from "@/lib/utils";

type StickyScrollContent = {
  title: string;
  description: string;
  content?: React.ReactNode;
};

type StickyScrollProps = {
  content: StickyScrollContent[];
  contentClassName?: string;
};

export function StickyScroll({ content, contentClassName }: StickyScrollProps) {
  const [activeCard, setActiveCard] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    container: ref,
    //offset: ["start start", "end start"],
  });

  const cardLength = content.length;

  useMotionValueEvent(scrollYProgress, "change", (latest) => {
    if (cardLength <= 1) {
      setActiveCard(0);
      return;
    }
    const index = Math.floor(latest * (cardLength - 1));
    setActiveCard(Math.min(cardLength - 1, Math.max(0, index)));
  });

  const backgroundColors = [
    "var(--slate-900)",
    "var(--black)",
    "var(--neutral-900)",
  ];
  const linearGradients = [
    "linear-gradient(to bottom right, var(--cyan-500), var(--emerald-500))",
    "linear-gradient(to bottom right, var(--pink-500), var(--indigo-500))",
    "linear-gradient(to bottom right, var(--orange-500), var(--yellow-500))",
  ];

  const backgroundGradient =
    linearGradients[activeCard % linearGradients.length] ?? linearGradients[0];

  return (
    <motion.div
      animate={{
        backgroundColor: backgroundColors[activeCard % backgroundColors.length],
      }}
      className="scrollbar-hide relative flex h-[30rem] justify-center space-x-6 overflow-y-auto rounded-md px-4 py-4 md:space-x-10 md:px-8 md:py-8"
      ref={ref}
    >
      <div className="relative flex items-start px-4 pb-0">
        <div className="max-w-2xl">
          {content.map((item, index) => (
            <div key={`${item.title}-${index}`} className="my-10 md:my-16">
              {item.title ? (
                <motion.h2
                  initial={{
                    opacity: 0,
                  }}
                  animate={{
                    opacity: activeCard === index ? 1 : 0.3,
                  }}
                  className="text-2xl font-bold text-slate-100"
                >
                  {item.title}
                </motion.h2>
              ) : null}
              {item.description ? (
                <motion.p
                  initial={{
                    opacity: 0,
                  }}
                  animate={{
                    opacity: activeCard === index ? 1 : 0.3,
                  }}
                  className="mt-10 max-w-sm text-slate-300"
                >
                  {item.description}
                </motion.p>
              ) : null}
            </div>
          ))}
          <div className="h-8 md:h-16" />

        </div>
      </div>
      <div
        style={{ background: backgroundGradient }}
        className={cn(
          "sticky top-10 hidden h-60 w-80 overflow-hidden rounded-md bg-white lg:block",
          contentClassName
        )}
      >
        <motion.div
          key={activeCard}
          initial={{ opacity: 0, y: 4, scale: 0.995 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
          className="h-full w-full"
        >
          {content[activeCard].content ?? null}
        </motion.div>
      </div>
    </motion.div>
  );
}
