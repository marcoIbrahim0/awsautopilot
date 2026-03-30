"use client";

import { memo } from "react";
import { motion } from "motion/react";

import { buildBusinessImpactPanel } from "@/components/actionDetailBusinessImpact";
import { AnimatedTooltip } from "@/components/ui/AnimatedTooltip";
import {
  REMEDIATION_EYEBROW_CLASS,
  remediationInsetClass,
  remediationPanelClass,
} from "@/components/ui/remediation-surface";
import {
  buildPriorityStoryboardModel,
  type PriorityStoryboardEvidenceNode,
  type PriorityStoryboardFactor,
} from "@/components/actionDetailPriorityStoryboardModel";
import type { ActionBusinessImpact, ActionScoreFactor } from "@/lib/api";
import { cn } from "@/lib/utils";

const STORYBOARD_TRANSITION = {
  duration: 0.35,
  ease: [0.16, 1, 0.3, 1] as const,
};

const HELP_TEXT_TRIGGER_CLASS =
  "cursor-help items-center gap-1 rounded-lg text-info/90 underline decoration-dotted decoration-info/55 underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-info/40 after:inline-flex after:h-4 after:min-w-4 after:items-center after:justify-center after:rounded-full after:border after:border-info/35 after:px-1 after:text-[10px] after:font-semibold after:leading-none after:text-info/75 after:content-['?']";

const HELP_CHIP_TRIGGER_CLASS =
  "cursor-help items-center gap-1 rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-info/40 after:inline-flex after:h-4 after:min-w-4 after:items-center after:justify-center after:rounded-full after:border after:border-info/35 after:px-1 after:text-[10px] after:font-semibold after:leading-none after:text-info/75 after:content-['?']";

interface ActionDetailPriorityStoryboardProps {
  actionType?: string | null;
  businessImpact: ActionBusinessImpact;
  scoreFactors: ActionScoreFactor[];
}

function ActionDetailPriorityStoryboardComponent({
  actionType,
  businessImpact,
  scoreFactors,
}: ActionDetailPriorityStoryboardProps) {
  const businessImpactPanel = buildBusinessImpactPanel(
    businessImpact,
    actionType ?? undefined,
  );
  const storyboard = buildPriorityStoryboardModel(
    scoreFactors,
    businessImpact,
    businessImpactPanel,
  );

  return (
    <div className={remediationPanelClass("default", "p-8")}>
      <div className="mb-6 flex items-center gap-3">
        <div className={remediationInsetClass("accent", "w-fit p-2 text-info")}>
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"
            />
          </svg>
        </div>
        <h3 className="text-sm font-bold uppercase tracking-widest text-text/90">
          Why this is prioritized
        </h3>
      </div>

      <div className="space-y-6">
        <StoryboardHeadline
          headline={storyboard.headline}
          focusDimensionTooltip={storyboard.focusDimensionTooltip}
          primaryLabel={storyboard.primaryLabel}
        />

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(0,0.92fr)]">
          <ScoreWaterfall
            factors={storyboard.factors}
            scoreWaterfallTooltip={storyboard.scoreWaterfallTooltip}
            total={storyboard.activeContributionTotal}
            visibleLiftTooltip={storyboard.visibleLiftTooltip}
          />
          <ImpactConstellation
            evidenceNodes={storyboard.evidenceNodes}
            impactConstellationTooltip={storyboard.impactConstellationTooltip}
            primaryDetail={storyboard.primaryDetail}
            primaryLabel={storyboard.primaryLabel}
          />
        </div>

        <CommandRail
          commandText={storyboard.commandText}
          contextBadge={storyboard.contextBadge}
          contextBadgeTooltip={storyboard.contextBadgeTooltip}
        />
      </div>
    </div>
  );
}

export const ActionDetailPriorityStoryboard = memo(
  ActionDetailPriorityStoryboardComponent,
);

function CommandRail({
  commandText,
  contextBadge,
  contextBadgeTooltip,
}: {
  commandText: string;
  contextBadge: string | null;
  contextBadgeTooltip: string | null;
}) {
  return (
    <section
      className={remediationPanelClass("accent", "overflow-hidden")}
      data-testid="priority-storyboard-command"
    >
      <div className="flex flex-col gap-4 border-b border-border/30 px-5 py-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-4">
          <div
            className={remediationInsetClass(
              "accent",
              "mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center p-0 text-accent",
            )}
          >
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12.75L11.25 15 15 9.75"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M20.25 12a8.25 8.25 0 11-16.5 0 8.25 8.25 0 0116.5 0z"
              />
            </svg>
          </div>
          <div className="space-y-2">
            <p className={REMEDIATION_EYEBROW_CLASS}>Recommended next step</p>
            <p className="max-w-2xl text-sm leading-7 text-text/74">
              Start with this operator check before generating a bundle or suppressing the action.
            </p>
          </div>
        </div>

        {contextBadge && (
          <AnimatedTooltip
            content={contextBadgeTooltip}
            autoFlip
            focusable
            maxWidth="420px"
            placement="bottom"
            tapToToggle
            triggerClassName={HELP_CHIP_TRIGGER_CLASS}
          >
            <div className={remediationInsetClass("warning", "flex flex-wrap items-center gap-2 px-4 py-2.5")}>
              <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-warning/90">
                Context missing
              </span>
              <span className="text-xs leading-relaxed text-text/78">
                {contextBadge}
              </span>
            </div>
          </AnimatedTooltip>
        )}
      </div>

      <div className="px-5 py-5">
        <div className={remediationInsetClass("default", "flex items-start gap-4 bg-[var(--card)]/86 px-5 py-4")}>
          <div className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-accent shadow-[0_0_0_6px_rgba(10,113,255,0.12)] dark:shadow-[0_0_0_6px_rgba(10,113,255,0.18)]" />
          <p className="text-[15px] font-semibold leading-8 text-text/96">
            {commandText}
          </p>
        </div>
      </div>
    </section>
  );
}

function ConstellationNode({ detail, title }: PriorityStoryboardEvidenceNode) {
  return (
    <motion.div
      className={remediationInsetClass("default", "p-4")}
      initial={{ opacity: 0, scale: 0.98, y: 6 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={STORYBOARD_TRANSITION}
    >
      <p className={REMEDIATION_EYEBROW_CLASS}>
        {title}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-text/84">{detail}</p>
    </motion.div>
  );
}

function ImpactConstellation({
  evidenceNodes,
  impactConstellationTooltip,
  primaryDetail,
  primaryLabel,
}: {
  evidenceNodes: PriorityStoryboardEvidenceNode[];
  impactConstellationTooltip: string;
  primaryDetail: string | null;
  primaryLabel: string | null;
}) {
  const secondaryEvidence = evidenceNodes.slice(1);

  return (
    <section
      className={remediationInsetClass("default", "p-6")}
      data-testid="priority-storyboard-constellation"
    >
      <div className="space-y-2">
        <AnimatedTooltip
          content={impactConstellationTooltip}
          autoFlip
          focusable
          maxWidth="420px"
          placement="bottom"
          tapToToggle
          triggerClassName={HELP_TEXT_TRIGGER_CLASS}
        >
          <p className={REMEDIATION_EYEBROW_CLASS}>
            Impact constellation
          </p>
        </AnimatedTooltip>
        <p className="text-sm leading-relaxed text-text/80">
          The strongest business context signal is anchored on the right. Any
          additional matched signals stay grouped beside it as supporting
          evidence.
        </p>
      </div>

      {primaryLabel ? (
        <div
          className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,0.84fr)_minmax(0,1.16fr)]"
          data-testid="priority-storyboard-evidence-grid"
        >
          <div className="space-y-3">
            {secondaryEvidence.length > 0 ? (
              secondaryEvidence.map((node) => (
                <ConstellationNode key={node.id} {...node} />
              ))
            ) : null}
          </div>

          <motion.div
            className={remediationPanelClass("accent", "p-6")}
            data-testid="priority-storyboard-primary-node"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={STORYBOARD_TRANSITION}
          >
            <p className={REMEDIATION_EYEBROW_CLASS}>
              Primary dimension
            </p>
            <p className="mt-2 text-2xl font-semibold leading-tight text-text">
              {primaryLabel}
            </p>

            <div className={remediationInsetClass("default", "mt-5 p-4")}>
              <p className={REMEDIATION_EYEBROW_CLASS}>
                Why it matters
              </p>
              <p className="mt-2 text-sm leading-relaxed text-text/84">
                {primaryDetail ??
                  "This is the strongest currently matched business context signal for the action."}
              </p>
            </div>

          </motion.div>
        </div>
      ) : (
        <div className={remediationInsetClass("default", "mt-5 p-5")}>
          <p className={REMEDIATION_EYEBROW_CLASS}>
            Business context pending
          </p>
          <p className="mt-2 text-sm leading-relaxed text-text/78">
            No matched business dimensions are verified for this action yet.
            Priority remains driven by technical risk until tenant context is
            enriched.
          </p>
        </div>
      )}
    </section>
  );
}

function factorToneClasses(factor: PriorityStoryboardFactor): {
  chipClass: string;
  fillClass: string;
  valueClass: string;
} {
  if (factor.muted) {
    return {
      chipClass: "border-border/30 bg-surface/40",
      fillClass:
        "bg-surface/60 border border-border/40",
      valueClass: "text-muted",
    };
  }

  if (factor.key === "severity") {
    return {
      chipClass: "border-danger/20 bg-danger/5",
      fillClass:
        "bg-danger/25 border border-danger/35 shadow-[0_0_24px_rgba(239,68,68,0.16)]",
      valueClass: "text-danger",
    };
  }

  if (factor.key === "internet_exposure") {
    return {
      chipClass: "border-warning/20 bg-warning/5",
      fillClass:
        "bg-warning/25 border border-warning/35 shadow-[0_0_24px_rgba(245,158,11,0.14)]",
      valueClass: "text-warning",
    };
  }

  if (factor.key === "privilege_level") {
    return {
      chipClass: "border-info/20 bg-info/5",
      fillClass:
        "bg-info/22 border border-info/35 shadow-[0_0_24px_rgba(59,130,246,0.14)]",
      valueClass: "text-info",
    };
  }

  if (factor.key === "data_sensitivity") {
    return {
      chipClass: "border-emerald-500/20 bg-emerald-500/5",
      fillClass:
        "bg-emerald-500/20 border border-emerald-500/30 shadow-[0_0_24px_rgba(16,185,129,0.14)]",
      valueClass: "text-emerald-700",
    };
  }

  return {
    chipClass: "border-border/40 bg-white/5 dark:bg-accent/4",
    fillClass: "bg-accent/15 border border-accent/25",
    valueClass: "text-text/85",
  };
}

function ScoreWaterfall({
  factors,
  scoreWaterfallTooltip,
  total,
  visibleLiftTooltip,
}: {
  factors: PriorityStoryboardFactor[];
  scoreWaterfallTooltip: string;
  total: number;
  visibleLiftTooltip: string;
}) {
  return (
    <section
      className={remediationInsetClass("default", "p-6")}
      data-testid="priority-storyboard-waterfall"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="space-y-1">
          <AnimatedTooltip
            content={scoreWaterfallTooltip}
            autoFlip
            focusable
            maxWidth="420px"
            placement="bottom"
            tapToToggle
            triggerClassName={HELP_TEXT_TRIGGER_CLASS}
          >
            <p className={REMEDIATION_EYEBROW_CLASS}>
              Score waterfall
            </p>
          </AnimatedTooltip>
          <p className="text-xs leading-relaxed text-text/74">
            Strongest score drivers stay on the rail. Neutral or dampening
            inputs stay visible but muted.
          </p>
        </div>
        <AnimatedTooltip
          content={visibleLiftTooltip}
          autoFlip
          focusable
          maxWidth="420px"
          placement="bottom"
          tapToToggle
          triggerClassName={HELP_CHIP_TRIGGER_CLASS}
        >
          <span className="shrink-0 rounded-full border border-border/40 bg-surface/60 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-text/75">
            Visible lift +{total}
          </span>
        </AnimatedTooltip>
      </div>

      <div className="mt-5 space-y-3">
        {factors.length > 0 ? (
          factors.map((factor, index) => (
            <WaterfallFactorRow
              key={factor.key}
              factor={factor}
              index={index}
            />
          ))
        ) : (
          <div className="rounded-[1.25rem] border border-border/25 bg-surface/40 p-4 text-sm italic text-muted">
            Explainable score factors are not available for this action yet.
          </div>
        )}
      </div>
    </section>
  );
}

function StoryboardHeadline({
  headline,
  focusDimensionTooltip,
  primaryLabel,
}: {
  headline: string;
  focusDimensionTooltip: string | null;
  primaryLabel: string | null;
}) {
  return (
    <section
      className={remediationInsetClass("default", "p-6")}
      data-testid="priority-storyboard-headline"
    >
      <p className={REMEDIATION_EYEBROW_CLASS}>
        Priority storyboard
      </p>
      <p className="mt-2 text-lg font-semibold leading-snug text-text">
        {headline}
      </p>
      {primaryLabel && (
        <AnimatedTooltip
          content={focusDimensionTooltip}
          autoFlip
          focusable
          maxWidth="420px"
          placement="bottom"
          tapToToggle
          triggerClassName={HELP_TEXT_TRIGGER_CLASS}
        >
          <p className="mt-3 text-[11px] font-medium uppercase tracking-[0.14em] text-muted/70">
            Focus dimension:{" "}
            <span className="text-text/82">{primaryLabel}</span>
          </p>
        </AnimatedTooltip>
      )}
    </section>
  );
}

function WaterfallFactorRow({
  factor,
  index,
}: {
  factor: PriorityStoryboardFactor;
  index: number;
}) {
  const tone = factorToneClasses(factor);
  const width = `${Math.max(factor.laneWidthPercent, factor.muted ? 10 : 14)}%`;

  return (
    <div
      className={cn(remediationInsetClass("default", "p-4"), tone.chipClass)}
      data-factor-tone={factor.muted ? "muted" : "active"}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <AnimatedTooltip
          content={factor.tooltip}
          autoFlip
          focusable
          maxWidth="420px"
          placement="bottom"
          tapToToggle
          triggerClassName={HELP_TEXT_TRIGGER_CLASS}
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text/82">
            {factor.label}
          </p>
        </AnimatedTooltip>
        <span className={`shrink-0 text-sm font-bold ${tone.valueClass}`}>
          {formatContribution(factor.contribution)}
        </span>
      </div>
      <div className="relative h-3 overflow-hidden rounded-full border border-border/40 bg-surface/30">
        <motion.div
          className="absolute inset-y-0"
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ ...STORYBOARD_TRANSITION, delay: index * 0.05 }}
          style={{
            left: `${factor.muted ? 0 : factor.laneStartPercent}%`,
            width,
          }}
        >
          <div className={`h-full rounded-full ${tone.fillClass}`} />
        </motion.div>
      </div>
    </div>
  );
}

function formatContribution(value: number): string {
  if (value > 0) return `+${value}`;
  return `${value}`;
}
