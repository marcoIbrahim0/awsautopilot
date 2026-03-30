"use client";

import { memo } from "react";

import { REMEDIATION_EYEBROW_CLASS, remediationInsetClass } from "@/components/ui/remediation-surface";
import type { ActionAttackPathFact, ActionAttackPathNode } from "@/lib/api";

function titleCaseToken(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatAttackPathBadgeLabel(badge: string): string {
  if (badge === "actively_exploited") return "Actively exploited";
  if (badge === "business_critical") return "Business critical";
  if (badge === "recommended") return "Safest next step";
  if (badge === "context_incomplete") return "Context incomplete";
  return titleCaseToken(badge);
}

function getAttackPathFactValueClass(
  tone: ActionAttackPathFact["tone"],
): string {
  if (tone === "accent") return "font-semibold text-danger/90";
  if (tone === "code") {
    return "break-all font-mono text-[12px] leading-6 text-text/82";
  }
  return "font-medium text-text/82";
}

interface ActionDetailAttackPathNodeCardProps {
  node: ActionAttackPathNode;
}

function ActionDetailAttackPathNodeCardComponent({
  node,
}: ActionDetailAttackPathNodeCardProps) {
  const badges = node.badges ?? [];
  const facts = node.facts ?? [];
  const visibleBadges = badges.filter(
    (badge) => !(node.kind === "next_step" && badge === "recommended"),
  );

  return (
    <div
      className={remediationInsetClass(
        node.kind === "target_asset" ? "danger" : "default",
        "flex h-full min-h-[17rem] w-[19rem] flex-col p-5",
      )}
    >
      <div className="flex flex-1 flex-col">
        <span className={REMEDIATION_EYEBROW_CLASS}>
          {titleCaseToken(node.kind)}
        </span>
        <p
          className="mt-3 text-lg font-semibold leading-8 text-text break-words"
          title={node.label}
        >
          {node.label}
        </p>
        {node.detail && (
          <p
            className={`mt-3 text-sm leading-7 ${
              node.kind === "target_asset"
                ? "font-medium text-danger/78"
                : "text-text/68"
            }`}
          >
            {node.detail}
          </p>
        )}
        {facts.length > 0 && (
          <dl className="mt-5 space-y-3 border-t border-border/35 pt-4">
            {facts.map((fact) => (
              <div
                key={`${node.node_id}-${fact.label}-${fact.value}`}
                className="grid grid-cols-[4.5rem_minmax(0,1fr)] items-start gap-3 text-xs"
              >
                <dt className="pt-0.5 uppercase tracking-[0.16em] text-muted/60">
                  {fact.label}
                </dt>
                <dd className={getAttackPathFactValueClass(fact.tone)}>
                  {fact.value}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
      {visibleBadges.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {visibleBadges.map((badge) => (
            <span
              key={badge}
              className="rounded-full border border-border/55 bg-bg/70 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-text/72"
            >
              {formatAttackPathBadgeLabel(badge)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export const ActionDetailAttackPathNodeCard = memo(
  ActionDetailAttackPathNodeCardComponent,
);
