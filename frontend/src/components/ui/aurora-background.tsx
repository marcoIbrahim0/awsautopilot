"use client";

import { cn } from "@/lib/utils";
import React, { ReactNode } from "react";

interface AuroraBackgroundProps extends React.HTMLProps<HTMLDivElement> {
  children: ReactNode;
  showRadialGradient?: boolean;
  /** When true, always use dark aurora (ignores theme). Use for hero sections. */
  dark?: boolean;
}

/* Exact Aceternity-style dark aurora: same gradients, mask ellipse at 100% 0%, opacity 0.5, ::after 200% 100% + mix-blend-difference + animation */
const darkAuroraVars = {
  "--aurora":
    "repeating-linear-gradient(100deg,#3b82f6 10%,#a5b4fc 15%,#93c5fd 20%,#ddd6fe 25%,#60a5fa 30%)",
  "--dark-gradient":
    "repeating-linear-gradient(100deg,#000 0%,#000 7%,transparent 10%,transparent 12%,#000 16%)",
  "--white-gradient":
    "repeating-linear-gradient(100deg,#fff 0%,#fff 7%,transparent 10%,transparent 12%,#fff 16%)",
  "--transparent": "transparent",
} as React.CSSProperties;

const darkAuroraMask = {
  maskImage: "radial-gradient(ellipse at 100% 0%, black 10%, transparent 70%)",
  WebkitMaskImage:
    "radial-gradient(ellipse at 100% 0%, black 10%, transparent 70%)",
};

export const AuroraBackground = ({
  className,
  children,
  showRadialGradient = true,
  dark = false,
  ...props
}: AuroraBackgroundProps) => {
  return (
    <div
      className={cn(
        "relative flex min-h-screen flex-col items-center justify-center bg-zinc-50 text-slate-950 dark:bg-zinc-900",
        dark && "text-[#fafafa]",
        className
      )}
      style={
        dark
          ? { backgroundColor: "#040817", color: "#fafafa" }
          : undefined
      }
      {...props}
    >
      <div
        className="absolute inset-0 overflow-hidden"
        style={dark ? darkAuroraVars : {
          "--aurora":
            "repeating-linear-gradient(100deg,#3b82f6_10%,#a5b4fc_15%,#93c5fd_20%,#ddd6fe_25%,#60a5fa_30%)",
          "--dark-gradient":
            "repeating-linear-gradient(100deg,#0a0a0f_0%,#0a0a0f_6%,transparent_8%,transparent_14%,#0a0a0f_18%)",
          "--white-gradient":
            "repeating-linear-gradient(100deg,#fff_0%,#fff_7%,transparent_10%,transparent_12%,#fff_16%)",
          "--transparent": "transparent",
        } as React.CSSProperties}
      >
        {dark ? (
          <div
            className={cn(
              "pointer-events-none absolute -inset-[10px] opacity-50 blur-[10px] will-change-transform",
              "aurora-layer-exact"
            )}
            style={{
              backgroundImage: "var(--dark-gradient), var(--aurora)",
              backgroundSize: "300% 200%",
              backgroundPosition: "50% 50%, 50% 50%",
              ...(showRadialGradient ? darkAuroraMask : {}),
            }}
          />
        ) : (
          <div
            className={cn(
              "aurora-bg-layer pointer-events-none absolute -inset-[10px] opacity-80 blur-[10px] will-change-transform",
              "after:absolute after:inset-0 after:content-[''] after:[background-attachment:fixed]",
              "[background-size:300%_200%] [background-position:50%_50%,50%_50%]",
              showRadialGradient &&
                "[mask-image:radial-gradient(ellipse_100%_80%_at_50%_50%,black_40%,var(--transparent)_70%)]",
              "invert [background-image:var(--white-gradient),var(--aurora)] after:[background-image:var(--white-gradient),var(--aurora)] after:mix-blend-difference",
              "dark:invert-0 dark:[background-image:var(--dark-gradient),var(--aurora)] after:dark:[background-image:var(--dark-gradient),var(--aurora)]"
            )}
          />
        )}
      </div>
      {children}
    </div>
  );
};
