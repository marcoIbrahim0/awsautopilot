"use client";

import type { ComponentProps } from "react";
import { FeatureCarousel } from "@/components/ui/feature-carousel";

type HowItWorksCarouselProps = ComponentProps<typeof FeatureCarousel>;

export function HowItWorksCarousel(props: HowItWorksCarouselProps) {
  return <FeatureCarousel {...props} />;
}
