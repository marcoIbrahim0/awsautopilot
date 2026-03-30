'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  completeRootKeyExternalTask,
  deleteRootKeyRemediationRun,
  disableRootKeyRemediationRun,
  getErrorMessage,
  getRootKeyRemediationRun,
  RootKeyArtifactSnapshot,
  RootKeyDependencySnapshot,
  RootKeyEventSnapshot,
  RootKeyExternalTaskSnapshot,
  RootKeyRunDetailResponse,
  rollbackRootKeyRemediationRun,
  validateRootKeyRemediationRun,
} from '@/lib/api';

const TERMINAL_STATES = new Set(['completed', 'rolled_back', 'failed']);
const POLL_BASE_MS = 2000;
const POLL_MAX_MS = 30000;

type WizardAction = 'validate' | 'disable' | 'rollback';

interface RootKeyRemediationLifecycleProps {
  runId: string;
  tenantId?: string;
  isAdmin: boolean;
}

function formatTimestamp(value: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleString();
}

function statusVariant(status: string): 'default' | 'info' | 'warning' | 'success' | 'danger' {
  const normalized = (status || '').toLowerCase();
  if (normalized === 'completed' || normalized === 'success') return 'success';
  if (normalized === 'failed' || normalized === 'cancelled') return 'danger';
  if (normalized === 'running') return 'info';
  if (normalized === 'waiting_for_user' || normalized === 'queued') return 'warning';
  return 'default';
}

function stateVariant(state: string): 'default' | 'info' | 'warning' | 'success' | 'danger' {
  const normalized = (state || '').toLowerCase();
  if (normalized === 'completed') return 'success';
  if (normalized === 'rolled_back' || normalized === 'failed') return 'danger';
  if (normalized === 'needs_attention') return 'warning';
  if (normalized === 'migration' || normalized === 'validation' || normalized === 'disable_window' || normalized === 'delete_window') {
    return 'info';
  }
  return 'default';
}

function getDependencyLabel(dependency: RootKeyDependencySnapshot): string {
  const payload = dependency.fingerprint_payload;
  if (!payload || Array.isArray(payload)) return dependency.fingerprint_type;
  const service = typeof payload.service === 'string' ? payload.service : null;
  const action = typeof payload.api_action === 'string' ? payload.api_action : null;
  if (service && action) return `${service} · ${action}`;
  return dependency.fingerprint_type;
}

function isHttpLink(ref: string | null): boolean {
  return Boolean(ref && /^https?:\/\//i.test(ref));
}

function transitionOptions(run: RootKeyRunDetailResponse | null): WizardAction[] {
  const state = run?.run.state;
  if (state === 'migration') return ['validate', 'rollback'];
  if (state === 'validation' || state === 'needs_attention') return ['disable', 'rollback'];
  return ['rollback'];
}

function summarizeEventEvidence(
  event: RootKeyEventSnapshot,
  artifacts: RootKeyArtifactSnapshot[],
): RootKeyArtifactSnapshot[] {
  return artifacts.filter((artifact) => artifact.state === event.state);
}

export function RootKeyRemediationLifecycle({
  runId,
  tenantId,
  isAdmin,
}: RootKeyRemediationLifecycleProps) {
  const [runDetail, setRunDetail] = useState<RootKeyRunDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [transitionError, setTransitionError] = useState<string | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);
  const [taskNotes, setTaskNotes] = useState<Record<string, string>>({});
  const [wizardStep, setWizardStep] = useState(1);
  const [wizardAck, setWizardAck] = useState(false);
  const [wizardAction, setWizardAction] = useState<WizardAction>('rollback');
  const [wizardError, setWizardError] = useState<string | null>(null);

  const refreshRun = useCallback(async () => {
    const detail = await getRootKeyRemediationRun(runId, { tenantId });
    setRunDetail(detail);
    setLoadError(null);
    setPollError(null);
    return detail;
  }, [runId, tenantId]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    let delay = POLL_BASE_MS;
    let hasLoadedData = false;

    const poll = async () => {
      try {
        const detail = await getRootKeyRemediationRun(runId, { tenantId });
        if (cancelled) return;
        hasLoadedData = true;
        setRunDetail(detail);
        setIsLoading(false);
        setLoadError(null);
        setPollError(null);
        delay = POLL_BASE_MS;
        if (!TERMINAL_STATES.has(detail.run.state)) {
          timer = window.setTimeout(poll, delay);
        }
      } catch (error) {
        if (cancelled) return;
        const message = getErrorMessage(error);
        setIsLoading(false);
        if (hasLoadedData) {
          setPollError(`Live updates paused: ${message}. Retrying with backoff.`);
        } else {
          setLoadError(message);
        }
        delay = Math.min(Math.floor(delay * 1.8), POLL_MAX_MS);
        timer = window.setTimeout(poll, delay);
      }
    };

    setIsLoading(true);
    poll();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [runId, tenantId]);

  const run = runDetail?.run ?? null;
  const isTerminal = run ? TERMINAL_STATES.has(run.state) : false;
  const canValidate = run?.state === 'migration';
  const canDisable = run?.state === 'validation' || run?.state === 'needs_attention';
  const canDelete = run?.state === 'disable_window' || run?.state === 'delete_window';
  const canRollback = Boolean(run) && !isTerminal;
  const unknownDependencies = useMemo(
    () => (runDetail?.dependencies ?? []).filter((dependency) => dependency.unknown_dependency),
    [runDetail?.dependencies],
  );
  const unresolvedTasks = useMemo(
    () => (runDetail?.external_tasks ?? []).filter((task) => task.status !== 'completed'),
    [runDetail?.external_tasks],
  );

  useEffect(() => {
    const options = transitionOptions(runDetail);
    if (!options.includes(wizardAction)) {
      setWizardAction(options[0]);
    }
  }, [runDetail, wizardAction]);

  const runTransition = useCallback(
    async (action: WizardAction, rollbackReason?: string) => {
      setTransitionError(null);
      setWizardError(null);
      setPendingAction(action);
      try {
        if (action === 'validate') {
          await validateRootKeyRemediationRun(runId, { tenantId });
        } else if (action === 'disable') {
          await disableRootKeyRemediationRun(runId, { tenantId });
        } else {
          await rollbackRootKeyRemediationRun(
            runId,
            { reason: rollbackReason || 'operator_requested_rollback' },
            { tenantId },
          );
        }
        await refreshRun();
      } catch (error) {
        const message = getErrorMessage(error);
        setTransitionError(message);
        setWizardError(message);
      } finally {
        setPendingAction(null);
      }
    },
    [refreshRun, runId, tenantId],
  );

  const completeTask = useCallback(
    async (task: RootKeyExternalTaskSnapshot) => {
      setTaskError(null);
      setPendingAction(`task:${task.id}`);
      try {
        const note = taskNotes[task.id]?.trim();
        await completeRootKeyExternalTask(
          runId,
          task.id,
          {
            result: {
              note: note || 'Completed via root-key lifecycle UI',
              completed_in_ui: true,
            },
          },
          { tenantId },
        );
        await refreshRun();
      } catch (error) {
        setTaskError(getErrorMessage(error));
      } finally {
        setPendingAction(null);
      }
    },
    [refreshRun, runId, taskNotes, tenantId],
  );

  const submitUnknownDependencyWizard = useCallback(async () => {
    if (!wizardAck) {
      setWizardError('You must acknowledge unknown dependency risk before continuing.');
      return;
    }
    if (wizardAction === 'rollback') {
      await runTransition('rollback', 'unknown_dependency_acknowledged_by_operator');
      return;
    }
    await runTransition(wizardAction);
  }, [runTransition, wizardAck, wizardAction]);

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-surface p-6">
        <div className="animate-pulse space-y-3">
          <div className="h-6 w-1/3 rounded bg-border" />
          <div className="h-4 w-full rounded bg-border" />
          <div className="h-4 w-3/4 rounded bg-border" />
        </div>
      </div>
    );
  }

  if (loadError || !runDetail || !run) {
    return (
      <div className="rounded-xl border border-danger/20 bg-danger/10 p-4">
        <p className="text-sm font-medium text-danger">Unable to load root-key remediation run</p>
        <p className="mt-1 text-xs text-danger/80">{loadError ?? 'Unexpected response shape.'}</p>
        <Button
          variant="secondary"
          size="sm"
          className="mt-3"
          onClick={() => {
            setIsLoading(true);
            void refreshRun().finally(() => setIsLoading(false));
          }}
        >
          Retry
        </Button>
      </div>
    );
  }

  const timeline = runDetail.events.length
    ? runDetail.events
    : [
        {
          id: `fallback-${run.id}`,
          run_id: run.id,
          event_type: 'run_created',
          state: run.state,
          status: run.status,
          rollback_reason: run.rollback_reason,
          created_at: run.created_at,
          completed_at: run.completed_at,
        },
      ];

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-surface p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={stateVariant(run.state)}>{run.state}</Badge>
          <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
          <span className="text-xs text-muted">Run: {run.id}</span>
        </div>
        <div className="mt-2 text-xs text-muted">
          Started {formatTimestamp(run.started_at)} · Updated {formatTimestamp(run.updated_at)}
        </div>
        {pollError && (
          <div className="mt-3 rounded-lg border border-warning/30 bg-warning/10 p-2 text-xs text-warning">
            {pollError}
          </div>
        )}
        {!isAdmin && (
          <div className="mt-3 rounded-lg border border-info/30 bg-info/10 p-2 text-xs text-info">
            Read-only mode. Admin role is required for transitions and task completion.
          </div>
        )}
      </div>

      <section className="rounded-xl border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-text">Run Timeline</h2>
          <span className="text-xs text-muted">{timeline.length} events</span>
        </div>
        <div className="space-y-3">
          {timeline.map((event) => {
            const eventArtifacts = summarizeEventEvidence(event, runDetail.artifacts);
            return (
              <div key={event.id} className="rounded-lg border border-border/70 bg-bg p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={stateVariant(event.state)}>{event.state}</Badge>
                  <Badge variant={statusVariant(event.status)}>{event.status}</Badge>
                  <span className="text-xs text-muted">{event.event_type}</span>
                  <span className="ml-auto text-xs text-muted">{formatTimestamp(event.created_at)}</span>
                </div>
                <div className="mt-2 space-y-1">
                  {eventArtifacts.length === 0 && (
                    <p className="text-xs text-muted">No evidence links recorded for this state.</p>
                  )}
                  {eventArtifacts.map((artifact) => (
                    <div key={artifact.id} className="text-xs">
                      {isHttpLink(artifact.artifact_ref) ? (
                        <a
                          href={artifact.artifact_ref ?? '#'}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-accent hover:underline"
                        >
                          {artifact.artifact_type} evidence
                        </a>
                      ) : artifact.artifact_ref ? (
                        <span className="font-mono text-muted">{artifact.artifact_ref}</span>
                      ) : (
                        <span className="text-muted">{artifact.artifact_type} (no link)</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-text">Dependency Checks</h2>
          <span className="text-xs text-muted">{runDetail.dependency_count} snapshots</span>
        </div>
        {runDetail.dependencies.length === 0 ? (
          <p className="text-sm text-muted">No dependency fingerprints were captured for this run.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                  <th className="pb-2 pr-2">Dependency</th>
                  <th className="pb-2 pr-2">Status</th>
                  <th className="pb-2 pr-2">Type</th>
                  <th className="pb-2">Captured</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/70">
                {runDetail.dependencies.map((dependency) => (
                  <tr key={dependency.id}>
                    <td className="py-2 pr-2 text-text">{getDependencyLabel(dependency)}</td>
                    <td className="py-2 pr-2">
                      <Badge variant={dependency.unknown_dependency ? 'warning' : 'success'}>
                        {dependency.unknown_dependency ? 'unknown' : 'managed'}
                      </Badge>
                    </td>
                    <td className="py-2 pr-2 text-muted">{dependency.status}</td>
                    <td className="py-2 text-muted">{formatTimestamp(dependency.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {unknownDependencies.length > 0 && (
        <section className="rounded-xl border border-warning/30 bg-warning/10 p-4">
          <h2 className="text-sm font-semibold text-warning">Action Required: Unknown Dependencies</h2>
          <p className="mt-1 text-xs text-warning/80">
            Review unknown dependencies before continuing. Choose a safe next step using the wizard below.
          </p>
          <div className="mt-3 text-xs text-warning/90">
            Step {wizardStep} of 3
          </div>

          {wizardStep === 1 && (
            <div className="mt-3 space-y-2">
              {unknownDependencies.map((dependency) => (
                <div key={dependency.id} className="rounded border border-warning/30 bg-warning/5 p-2">
                  <p className="text-xs font-medium text-text">{getDependencyLabel(dependency)}</p>
                  <p className="text-xs text-muted">Reason: {dependency.unknown_reason || 'unknown'}</p>
                </div>
              ))}
            </div>
          )}

          {wizardStep === 2 && (
            <div className="mt-3 rounded border border-warning/30 bg-warning/5 p-3">
              <label className="flex items-start gap-2 text-sm text-text">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 accent-[var(--color-accent)]"
                  checked={wizardAck}
                  onChange={(event) => setWizardAck(event.target.checked)}
                />
                I reviewed unknown dependencies and accept that forward progress should remain fail-closed unless an admin confirms next action.
              </label>
            </div>
          )}

          {wizardStep === 3 && (
            <div className="mt-3 space-y-2">
              {transitionOptions(runDetail).map((option) => (
                <label key={option} className="flex items-center gap-2 text-sm text-text">
                  <input
                    type="radio"
                    name="unknown-dependency-action"
                    checked={wizardAction === option}
                    onChange={() => setWizardAction(option)}
                  />
                  {option === 'validate' && 'Resume to validation'}
                  {option === 'disable' && 'Move to disable window'}
                  {option === 'rollback' && 'Rollback run'}
                </label>
              ))}
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setWizardStep((step) => Math.max(step - 1, 1))}
              disabled={wizardStep === 1}
            >
              Back
            </Button>
            {wizardStep < 3 ? (
              <Button variant="secondary" size="sm" onClick={() => setWizardStep((step) => Math.min(step + 1, 3))}>
                Next
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                disabled={!isAdmin || pendingAction !== null}
                onClick={() => {
                  void submitUnknownDependencyWizard();
                }}
              >
                {pendingAction ? 'Submitting…' : 'Submit decision'}
              </Button>
            )}
          </div>
          {wizardError && <p className="mt-2 text-xs text-danger">{wizardError}</p>}
        </section>
      )}

      <section className="rounded-xl border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-text">External Migration Tasks</h2>
          <span className="text-xs text-muted">{runDetail.external_tasks.length} tasks</span>
        </div>
        {runDetail.external_tasks.length === 0 ? (
          <p className="text-sm text-muted">No external tasks required for this run.</p>
        ) : (
          <div className="space-y-3">
            {runDetail.external_tasks.map((task) => (
              <div key={task.id} className="rounded-lg border border-border/70 bg-bg p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={statusVariant(task.status)}>{task.status}</Badge>
                  <span className="text-sm text-text">{task.task_type}</span>
                  <span className="ml-auto text-xs text-muted">Due {formatTimestamp(task.due_at)}</span>
                </div>
                {task.status !== 'completed' && (
                  <div className="mt-2 space-y-2">
                    <textarea
                      value={taskNotes[task.id] ?? ''}
                      onChange={(event) => {
                        setTaskNotes((previous) => ({ ...previous, [task.id]: event.target.value }));
                      }}
                      placeholder="Completion evidence summary (no secrets)"
                      className="w-full rounded-lg border border-border bg-surface p-2 text-sm text-text"
                      rows={3}
                      disabled={!isAdmin}
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => {
                        void completeTask(task);
                      }}
                      disabled={!isAdmin || pendingAction !== null}
                    >
                      {pendingAction === `task:${task.id}` ? 'Completing…' : 'Complete task'}
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        {taskError && <p className="mt-2 text-xs text-danger">{taskError}</p>}
      </section>

      <section className="rounded-xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-text">Run Controls</h2>
        <p className="mt-1 text-xs text-muted">
          Transitions are idempotent. Repeat clicks are safe and replay-protected by `Idempotency-Key`.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={!isAdmin || !canValidate || pendingAction !== null}
            onClick={() => {
              void runTransition('validate');
            }}
          >
            {pendingAction === 'validate' ? 'Transitioning…' : 'Validate'}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={!isAdmin || !canDisable || pendingAction !== null}
            onClick={() => {
              void runTransition('disable');
            }}
          >
            {pendingAction === 'disable' ? 'Transitioning…' : 'Disable Window'}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={!isAdmin || !canDelete || pendingAction !== null}
            onClick={() => {
              setPendingAction('delete');
              void deleteRootKeyRemediationRun(runId, { tenantId })
                .then(() => refreshRun())
                .catch((error) => setTransitionError(getErrorMessage(error)))
                .finally(() => setPendingAction(null));
            }}
          >
            {pendingAction === 'delete' ? 'Transitioning…' : 'Finalize Delete'}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={!isAdmin || !canRollback || pendingAction !== null}
            onClick={() => {
              void runTransition('rollback', 'operator_requested_rollback');
            }}
          >
            {pendingAction === 'rollback' ? 'Transitioning…' : 'Rollback'}
          </Button>
        </div>
        {transitionError && <p className="mt-2 text-xs text-danger">{transitionError}</p>}
      </section>

      {(run.state === 'rolled_back' || run.rollback_reason) && (
        <section className="rounded-xl border border-warning/30 bg-warning/10 p-4">
          <h2 className="text-sm font-semibold text-warning">Rollback Guidance</h2>
          <p className="mt-1 text-sm text-warning/90">
            This run is in rollback state. Confirm key status in AWS, capture rollback evidence, and re-run dependency discovery before retrying.
          </p>
          {run.rollback_reason && (
            <p className="mt-2 text-xs text-warning/80">
              Reason: <span className="font-mono">{run.rollback_reason}</span>
            </p>
          )}
        </section>
      )}

      {run.state === 'completed' && (
        <section className="rounded-xl border border-success/30 bg-success/10 p-4">
          <h2 className="text-sm font-semibold text-success">Completion Summary</h2>
          <div className="mt-2 grid grid-cols-1 gap-2 text-sm text-success/90 sm:grid-cols-2">
            <p>Dependencies captured: {runDetail.dependency_count}</p>
            <p>Timeline events: {runDetail.event_count}</p>
            <p>Evidence artifacts: {runDetail.artifact_count}</p>
            <p>Open external tasks: {unresolvedTasks.length}</p>
          </div>
          <p className="mt-2 text-xs text-success/80">
            Verify action/finding closure in the action detail view and store evidence links in the change ticket.
          </p>
        </section>
      )}
    </div>
  );
}
