import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type TextureVariant =
  | "fabric-of-squares"
  | "grid-noise"
  | "inflicted"
  | "debut-light"
  | "groovepaper"
  | "none";

const textureMap: Record<Exclude<TextureVariant, "none">, string> = {
  "fabric-of-squares": "https://www.cult-ui.com/textures/fabric-of-squares.png",
  "grid-noise": "https://www.cult-ui.com/textures/grid-noise.png",
  inflicted: "https://www.cult-ui.com/textures/inflicted.png",
  "debut-light": "https://www.cult-ui.com/textures/debut-light.png",
  groovepaper: "https://www.cult-ui.com/textures/groovepaper.png",
};

type BackgroundImageTextureProps = {
  variant?: TextureVariant;
  opacity?: number;
  className?: string;
  children?: ReactNode;
};

export function BackgroundImageTexture({
  variant = "fabric-of-squares",
  opacity = 0.5,
  className,
  children,
}: BackgroundImageTextureProps) {
  if (variant === "none") {
    return <div className={cn("relative", className)}>{children}</div>;
  }

  const textureUrl = textureMap[variant];

  return (
    <div className={cn("relative", className)}>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-0 bg-repeat"
        style={{
          backgroundImage: `url(${textureUrl})`,
          backgroundSize: "320px 320px",
          opacity,
        }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
