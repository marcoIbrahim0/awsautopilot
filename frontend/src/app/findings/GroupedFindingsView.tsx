'use client';

import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { FindingGroup, FindingGroupActionResponse, FindingGroupsFilters } from '@/lib/api';
import {
  classifyFindingGroupRemediationFocus,
  getRemediationFocusPresentation,
  REMEDIATION_FOCUS_ORDER,
  type RemediationFocusBucket,
} from '@/lib/remediationFocus';
import { FindingGroupCard } from './FindingGroupCard';
import { GroupingDimension } from './GroupingControlBar';

const SEVERITY_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMATIONAL'] as const;

interface GroupingNode {
  children: GroupingNode[];
  dim: GroupingDimension;
  groups: FindingGroup[];
  key: string;
}

function getDominantSeverity(dist: Record<string, number>): string {
  for (const sev of SEVERITY_ORDER) {
    if ((dist[sev] ?? 0) > 0) return sev;
  }
  return 'INFORMATIONAL';
}

function getBucketKey(group: FindingGroup, dim: GroupingDimension): string {
  switch (dim) {
    case 'severity':
      return getDominantSeverity(group.severity_distribution);
    case 'rule':
      return group.control_id || 'Unknown';
    case 'region':
      return group.regions.length === 1 ? group.regions[0] : group.regions.length > 1 ? 'Multiple regions' : 'Unknown';
    case 'resource':
      return group.resource_type
        ? group.resource_type.replace('AWS::', '').replace('::', ' › ')
        : 'Untyped resource';
    case 'status':
      return group.remediation_action_status ?? 'No action';
    case 'remediation':
      return getRemediationFocusPresentation(classifyFindingGroupRemediationFocus(group)).label;
  }
}

function bucketSortKey(dim: GroupingDimension, key: string): string {
  if (dim === 'remediation') {
    const order = REMEDIATION_FOCUS_ORDER.findIndex(
      (bucket) => getRemediationFocusPresentation(bucket).label === key
    );
    return order >= 0 ? String(order).padStart(2, '0') : '99';
  }
  if (dim !== 'severity') return key.toLowerCase();
  const idx = SEVERITY_ORDER.indexOf(key as typeof SEVERITY_ORDER[number]);
  return idx >= 0 ? String(idx).padStart(2, '0') : '99';
}

function bucketHeaderStyle(dim: GroupingDimension, key: string): string {
  if (dim !== 'severity') return 'text-text';
  if (key === 'CRITICAL') return 'text-danger';
  if (key === 'HIGH') return 'text-warning';
  if (key === 'MEDIUM') return 'text-accent';
  return 'text-muted';
}

function remediationBucketForLabel(key: string): RemediationFocusBucket | null {
  return (
    REMEDIATION_FOCUS_ORDER.find(
      (bucket) => getRemediationFocusPresentation(bucket).label === key
    ) || null
  );
}

function bucketDescription(dim: GroupingDimension, key: string): string | null {
  if (dim !== 'remediation') return null;
  const bucket = remediationBucketForLabel(key);
  if (!bucket) return null;
  return getRemediationFocusPresentation(bucket).description;
}

function buildGroupingNodes(groups: FindingGroup[], dims: GroupingDimension[]): GroupingNode[] {
  const [dim, ...rest] = dims;
  if (!dim) return [];
  const buckets = new Map<string, FindingGroup[]>();
  for (const group of groups) {
    const key = getBucketKey(group, dim);
    buckets.set(key, [...(buckets.get(key) ?? []), group]);
  }
  return Array.from(buckets.entries())
    .sort(([a], [b]) => bucketSortKey(dim, a).localeCompare(bucketSortKey(dim, b)))
    .map(([key, bucketGroups]) => ({
      key,
      dim,
      groups: bucketGroups,
      children: buildGroupingNodes(bucketGroups, rest),
    }));
}

interface GroupingBucketProps {
  defaultOpen?: boolean;
  effectiveTenantId?: string;
  groupActionFilters?: FindingGroupsFilters;
  groupActionsEnabled?: boolean;
  level: number;
  node: GroupingNode;
  onActionSelect?: (actionId: string) => void;
  onGroupActionComplete?: (result: FindingGroupActionResponse) => void;
}

function GroupingBucket({
  defaultOpen = true,
  effectiveTenantId,
  groupActionFilters,
  groupActionsEnabled,
  level,
  node,
  onActionSelect,
  onGroupActionComplete,
}: GroupingBucketProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const hasChildren = node.children.length > 0;
  const headerStyle = bucketHeaderStyle(node.dim, node.key);
  const findingsCount = node.groups.reduce((sum, group) => sum + group.finding_count, 0);
  const paddingClass = level === 0 ? 'px-8 py-6' : 'px-6 py-5';

  return (
    <div className={`rounded-[2.5rem] nm-neu-sm border-none overflow-hidden ${level === 0 ? 'mb-8' : 'mb-4'}`}>
      <button
        onClick={() => setIsOpen((value) => !value)}
        className={`w-full flex items-center justify-between ${paddingClass} transition-all border-none ${headerStyle}`}
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl nm-neu-pressed ${headerStyle}`}>
            <svg
              className={`w-4 h-4 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </div>
          <div>
            <span className="font-bold text-base tracking-tight block">{node.key}</span>
            <span className="text-xs font-semibold opacity-90">
              {node.groups.length} {node.groups.length === 1 ? 'group' : 'groups'} {' · '} {findingsCount} findings
            </span>
            {bucketDescription(node.dim, node.key) ? (
              <span className="mt-1 block text-xs font-medium opacity-80">
                {bucketDescription(node.dim, node.key)}
              </span>
            ) : null}
          </div>
        </div>
        <div className="nm-neu-sm px-4 py-1.5 rounded-xl text-[10px] font-bold uppercase tracking-widest opacity-70 hover:opacity-100 transition-opacity">
          {isOpen ? 'Collapse' : 'Expand'}
        </div>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key={`${node.dim}-${node.key}`}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className={`bg-transparent ${hasChildren ? 'p-3 space-y-3' : 'p-3 space-y-3'}`}>
              {hasChildren
                ? node.children.map((child, idx) => (
                    <GroupingBucket
                      key={`${node.dim}-${node.key}-${child.dim}-${child.key}`}
                      node={child}
                      level={level + 1}
                      defaultOpen={level > 0 || idx === 0}
                      effectiveTenantId={effectiveTenantId}
                      onActionSelect={onActionSelect}
                      groupActionFilters={groupActionFilters}
                      onGroupActionComplete={onGroupActionComplete}
                      groupActionsEnabled={groupActionsEnabled}
                    />
                  ))
                : node.groups.map((group) => (
                    <FindingGroupCard
                      key={group.group_key}
                      group={group}
                      effectiveTenantId={effectiveTenantId}
                      onActionSelect={onActionSelect}
                      groupActionFilters={groupActionFilters}
                      onGroupActionComplete={onGroupActionComplete}
                      groupActionsEnabled={groupActionsEnabled}
                    />
                  ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export interface GroupedFindingsViewProps {
  effectiveTenantId?: string;
  groupActionFilters?: FindingGroupsFilters;
  groupActionsEnabled?: boolean;
  groupingDimensions: GroupingDimension[];
  groups: FindingGroup[];
  onActionSelect?: (actionId: string) => void;
  onGroupActionComplete?: (result: FindingGroupActionResponse) => void;
}

export function GroupedFindingsView({
  effectiveTenantId,
  groupActionFilters,
  groupActionsEnabled,
  groupingDimensions,
  groups,
  onActionSelect,
  onGroupActionComplete,
}: GroupedFindingsViewProps) {
  const nodes = useMemo(() => buildGroupingNodes(groups, groupingDimensions), [groupingDimensions, groups]);

  if (groupingDimensions.length === 0 || nodes.length === 0) {
    return (
      <div className="space-y-3">
        {groups.map((group) => (
          <FindingGroupCard
            key={group.group_key}
            group={group}
            effectiveTenantId={effectiveTenantId}
            onActionSelect={onActionSelect}
            groupActionFilters={groupActionFilters}
            onGroupActionComplete={onGroupActionComplete}
            groupActionsEnabled={groupActionsEnabled}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {nodes.map((node, idx) => (
        <GroupingBucket
          key={`${node.dim}-${node.key}`}
          node={node}
          level={0}
          defaultOpen={idx === 0}
          effectiveTenantId={effectiveTenantId}
          onActionSelect={onActionSelect}
          groupActionFilters={groupActionFilters}
          onGroupActionComplete={onGroupActionComplete}
          groupActionsEnabled={groupActionsEnabled}
        />
      ))}
    </div>
  );
}
