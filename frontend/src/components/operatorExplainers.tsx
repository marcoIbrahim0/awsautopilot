'use client';

import type { ReactNode } from 'react';

import {
  buildBusinessCriticalExplainer,
  buildBusinessImpactBadgeExplainer,
  buildContextMissingExplainer,
  buildFocusDimensionExplainer,
  buildImpactConstellationExplainer,
  buildRiskScoreExplainer,
  buildScoreFactorExplainer,
  buildVisibleLiftExplainer,
  getBoundedDecisionViewExplainer,
  getScoreWaterfallExplainer,
} from '@/components/actionDetailExplainers';

export type ExplainerConceptId =
  | 'settings_surface'
  | 'settings_integrations'
  | 'settings_governance'
  | 'settings_remediation_defaults'
  | 'connected_aws_accounts'
  | 'connection_health'
  | 'read_role_posture'
  | 'monitored_regions'
  | 'validation_boundary'
  | 'onboarding_handoff'
  | 'lifecycle_timestamps'
  | 'required_service_checks'
  | 'account_id'
  | 'connection_status'
  | 'remediation_strategy'
  | 'blast_radius'
  | 'exception_path'
  | 'strategy_inputs'
  | 'dependency_checks'
  | 'precheck_result'
  | 'before_after_simulation'
  | 'execution_timing'
  | 'evidence_status'
  | 'suppression'
  | 'exception_reason'
  | 'exception_duration'
  | 'ticket_link'
  | 'remediation_run'
  | 'run_status'
  | 'run_mode'
  | 'progress_state'
  | 'implementation_artifacts'
  | 'evidence_pointers'
  | 'closure_checklist'
  | 'execution_log';

export type ExplainerContext =
  | 'default'
  | 'settings'
  | 'accounts'
  | 'remediation'
  | 'suppression'
  | 'run';

type ExplainerEntry = {
  content: ReactNode;
  label?: string;
  shortLabel?: string;
};

function contentWithContext(
  base: string,
  context: ExplainerContext,
  additions?: Partial<Record<ExplainerContext, string>>,
): string {
  const suffix = additions?.[context];
  return suffix ? `${base} ${suffix}` : base;
}

export function getExplainerContent(
  conceptId: ExplainerConceptId,
  context: ExplainerContext = 'default',
): ExplainerEntry {
  switch (conceptId) {
    case 'settings_surface':
      return {
        label: 'Settings surface',
        content: contentWithContext(
          'This is the operator control plane for tenant-wide defaults, access, integrations, and governance behavior.',
          context,
          {
            settings:
              'Use it to define the defaults that shape how findings, actions, remediation, and reporting behave across the workspace.',
          },
        ),
      };
    case 'settings_integrations':
      return {
        label: 'Integrations',
        content:
          'These settings control how the platform talks to systems like Jira, ServiceNow, and Slack. They shape outbound sync, inbound webhook handling, and whether follow-up work is created automatically.',
      };
    case 'settings_governance':
      return {
        label: 'Governance',
        content:
          'Governance settings control who gets escalations and where governance-specific notifications are sent. This is separate from weekly digest delivery.',
      };
    case 'settings_remediation_defaults':
      return {
        label: 'Remediation defaults',
        content:
          'These are tenant-wide defaults used when the platform generates remediation guidance or PR bundles. They reduce repeated operator input and keep strategy choices more consistent.',
      };
    case 'connected_aws_accounts':
      return {
        label: 'Connected AWS accounts',
        content:
          'This is the operational view of AWS accounts already connected to the tenant. It is for monitoring posture, refreshes, and lifecycle actions after onboarding begins.',
      };
    case 'connection_health':
      return {
        label: 'Connection health',
        content:
          'Connection health tells you whether the account is currently usable for ingest and platform operations. It is a live operator signal, not just a record that the account was once connected.',
      };
    case 'read_role_posture':
      return {
        label: 'ReadRole posture',
        content:
          'This explains whether the connected ReadRole and monitored-region scope still match what the platform expects. It helps you spot drift before ingest or validation problems show up elsewhere.',
      };
    case 'monitored_regions':
      return {
        label: 'Monitored regions',
        content:
          'These are the AWS regions the tenant chose to scan and operate against for this account. Findings and follow-up workflows only reflect the regions in this scope.',
      };
    case 'validation_boundary':
      return {
        label: 'Validation boundary',
        content:
          'This marks which checks stay in onboarding instead of Accounts. It keeps readiness proof explicit, so account operations do not silently imply that all prerequisite services are healthy.',
      };
    case 'onboarding_handoff':
      return {
        label: 'Onboarding handoff',
        content:
          'This means the account is connected here, but the final readiness proof still lives in onboarding. Use the handoff when you need to rerun required service checks or revalidate setup.',
      };
    case 'lifecycle_timestamps':
      return {
        label: 'Lifecycle timestamps',
        content:
          'These dates explain when the account was connected, updated, or last validated. They help operators judge whether the current posture is fresh or needs revalidation.',
      };
    case 'required_service_checks':
      return {
        label: 'Required service checks',
        content:
          'These are the AWS services the platform depends on for trustworthy ingest and remediation context. They stay explicit so operators know which prerequisites are blocking readiness.',
      };
    case 'account_id':
      return {
        label: 'Account ID',
        content:
          'This is the AWS account the platform is operating on. It is the main scope anchor for findings, actions, remediation runs, and onboarding checks.',
      };
    case 'connection_status':
      return {
        label: 'Connection status',
        content:
          'This shows whether the account is currently active in the platform or paused. A connected account can still need validation work, but a paused one is not being actively operated.',
      };
    case 'remediation_strategy':
      return {
        label: 'Remediation strategy',
        content:
          'This is the specific path the platform recommends for handling the action. It explains how the fix should be carried out, not just whether the issue matters.',
      };
    case 'blast_radius':
      return {
        label: 'Blast radius',
        content:
          'This describes how wide the change could reach if you execute the selected strategy. It helps you judge whether the fix affects one resource, a wider account setting, or operational access.',
      };
    case 'exception_path':
      return {
        label: 'Exception path',
        content:
          'This is the route for documenting why the issue should stay open or suppressed for now instead of being remediated. It records operator intent and sets a return point for later review.',
      };
    case 'strategy_inputs':
      return {
        label: 'Strategy inputs',
        content:
          'These are the extra values needed to generate a safe and specific remediation workflow for the chosen strategy. They shape the output but do not change the underlying issue itself.',
      };
    case 'dependency_checks':
      return {
        label: 'Dependency checks',
        content:
          'These checks explain what must already be true before the selected strategy is safe to run. They are there to prevent operators from creating a run that is incomplete or risky.',
      };
    case 'precheck_result':
      return {
        label: 'Pre-check result',
        content:
          'This shows what the platform sees about the current state before executing the remediation. It helps confirm whether the direct-fix path is appropriate right now.',
      };
    case 'before_after_simulation':
      return {
        label: 'Before / After simulation',
        content:
          'This is a bounded preview of the state transition the strategy is expected to create. It is meant to make the planned change easier to review before a run is created.',
      };
    case 'execution_timing':
      return {
        label: 'Execution timing',
        content:
          'This is the expected time window for the remediation and any follow-up verification to settle. It is a planning aid, not a guarantee.',
      };
    case 'evidence_status':
      return {
        label: 'Evidence status',
        content:
          'This shows whether the workflow has the proof it needs to support operator review or closure. Missing evidence usually means the remediation story is not yet fully documented.',
      };
    case 'suppression':
      return {
        label: 'Suppression',
        content:
          'Suppression removes the item from the active queue for a limited period without claiming that the underlying risk is fixed. It is for accepted risk, false positives, or temporary operator deferral.',
      };
    case 'exception_reason':
      return {
        label: 'Exception reason',
        content:
          'This explains why the issue is being suppressed instead of remediated. A good reason tells the next operator what decision was made and why it should be revisited later.',
      };
    case 'exception_duration':
      return {
        label: 'Exception duration',
        content:
          'This determines how long the suppression remains in effect before the issue returns to the active queue. It keeps exceptions time-bounded instead of becoming silent permanent exclusions.',
      };
    case 'ticket_link':
      return {
        label: 'Ticket link',
        content:
          'This connects the exception to the external work item that owns follow-up. It gives reviewers an audit trail back to the broader decision or maintenance process.',
      };
    case 'remediation_run':
      return {
        label: 'Remediation run',
        content:
          'A remediation run is the recorded execution workflow for a chosen fix path. It captures status, evidence, outputs, and closure proof around one remediation attempt.',
      };
    case 'run_status':
      return {
        label: 'Run status',
        content:
          'Run status tells you where the remediation attempt is in its lifecycle right now, such as queued, running, awaiting follow-up, or complete.',
      };
    case 'run_mode':
      return {
        label: 'Run mode',
        content:
          'Run mode explains what kind of remediation workflow was created, such as a PR-bundle handoff instead of a direct execution path.',
      };
    case 'progress_state':
      return {
        label: 'Progress state',
        content:
          'This is a simplified view of where the run is in execution. It helps operators orient quickly without reading the full activity log.',
      };
    case 'implementation_artifacts':
      return {
        label: 'Implementation artifacts',
        content:
          'These are the generated outputs or linked deliverables produced by the run, such as bundles or summaries. They are what an operator carries forward into the next system or workflow.',
      };
    case 'evidence_pointers':
      return {
        label: 'Evidence pointers',
        content:
          'Evidence pointers link the run to proof that the change happened or that follow-up validation was captured. They support operator review and later auditing.',
      };
    case 'closure_checklist':
      return {
        label: 'Closure checklist',
        content:
          'This is the bounded list of proof points the platform expects before the remediation can be treated as fully closed. It helps make closure explicit instead of assumed.',
      };
    case 'execution_log':
      return {
        label: 'Execution log',
        content:
          'This is the activity trail for the remediation attempt. It helps you see what happened, where it stalled, and what needs follow-up if the run did not finish cleanly.',
      };
    default: {
      const _exhaustive: never = conceptId;
      return { label: 'Explanation', content: _exhaustive };
    }
  }
}

export const actionDetailExplainerBridge = {
  buildBusinessCriticalExplainer,
  buildBusinessImpactBadgeExplainer,
  buildContextMissingExplainer,
  buildFocusDimensionExplainer,
  buildImpactConstellationExplainer,
  buildRiskScoreExplainer,
  buildScoreFactorExplainer,
  buildVisibleLiftExplainer,
  getBoundedDecisionViewExplainer,
  getScoreWaterfallExplainer,
};
