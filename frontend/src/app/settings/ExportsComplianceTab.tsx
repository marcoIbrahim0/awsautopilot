'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { Badge, getExportStatusBadgeVariant } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { DashboardTableCard } from '@/components/ui/remediation-surface';
import { useAuth } from '@/contexts/AuthContext';
import {
  createControlMapping,
  createExport,
  getErrorMessage,
  getExport,
  listControlMappings,
  listExports,
  type ControlMapping,
  type CreateControlMappingRequest,
  type ExportDetailResponse,
  type ExportListItem,
  type ExportPackType,
} from '@/lib/api';
import { SettingsCard, SettingsNotice, SettingsSectionIntro } from './settings-ui';

const POLL_INTERVAL_MS = 2500;
const TERMINAL_STATUSES = ['success', 'failed'];

function formatExportDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
  } catch {
    return iso;
  }
}

export function ExportsComplianceTab({
  panelId = 'settings-panel-exports-compliance',
}: {
  panelId?: string;
}) {
  const { user, isAuthenticated } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [exportPackType, setExportPackType] = useState<ExportPackType>('evidence');
  const [currentExportId, setCurrentExportId] = useState<string | null>(null);
  const [currentExportDetail, setCurrentExportDetail] = useState<ExportDetailResponse | null>(null);
  const [isCreatingExport, setIsCreatingExport] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [recentExports, setRecentExports] = useState<ExportListItem[]>([]);
  const [isLoadingExports, setIsLoadingExports] = useState(false);
  const exportPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [controlMappings, setControlMappings] = useState<ControlMapping[]>([]);
  const [controlMappingsTotal, setControlMappingsTotal] = useState(0);
  const [isLoadingControlMappings, setIsLoadingControlMappings] = useState(false);
  const [controlMappingsError, setControlMappingsError] = useState<string | null>(null);
  const [controlMappingFilterControlId, setControlMappingFilterControlId] = useState('');
  const [controlMappingFilterFramework, setControlMappingFilterFramework] = useState('');
  const [showAddMappingModal, setShowAddMappingModal] = useState(false);
  const [addMappingForm, setAddMappingForm] = useState<CreateControlMappingRequest>({
    control_id: '',
    framework_name: '',
    framework_control_code: '',
    control_title: '',
    description: '',
  });
  const [addMappingError, setAddMappingError] = useState<string | null>(null);
  const [addMappingSuccess, setAddMappingSuccess] = useState<string | null>(null);
  const [isAddingMapping, setIsAddingMapping] = useState(false);

  const fetchExports = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingExports(true);
    try {
      const { items } = await listExports({ limit: 10 });
      setRecentExports(items);
    } catch {
      setRecentExports([]);
    } finally {
      setIsLoadingExports(false);
    }
  }, [isAuthenticated]);

  const fetchControlMappings = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingControlMappings(true);
    setControlMappingsError(null);
    try {
      const { items, total } = await listControlMappings({
        limit: 100,
        offset: 0,
        ...(controlMappingFilterControlId.trim() ? { control_id: controlMappingFilterControlId.trim() } : {}),
        ...(controlMappingFilterFramework.trim() ? { framework_name: controlMappingFilterFramework.trim() } : {}),
      });
      setControlMappings(items);
      setControlMappingsTotal(total);
    } catch {
      setControlMappingsError('Failed to load control mappings. Please try again.');
    } finally {
      setIsLoadingControlMappings(false);
    }
  }, [controlMappingFilterControlId, controlMappingFilterFramework, isAuthenticated]);

  useEffect(() => {
    void fetchExports();
    void fetchControlMappings();
  }, [fetchControlMappings, fetchExports]);

  useEffect(() => {
    if (!currentExportId || !isAuthenticated) return;
    if (currentExportDetail && TERMINAL_STATUSES.includes(currentExportDetail.status)) return;

    const poll = async () => {
      try {
        const detail = await getExport(currentExportId);
        setCurrentExportDetail(detail);
        if (TERMINAL_STATUSES.includes(detail.status)) {
          if (exportPollRef.current) {
            clearInterval(exportPollRef.current);
            exportPollRef.current = null;
          }
          fetchExports();
        }
      } catch {
        if (exportPollRef.current) {
          clearInterval(exportPollRef.current);
          exportPollRef.current = null;
        }
      }
    };

    exportPollRef.current = setInterval(poll, POLL_INTERVAL_MS);
    void poll();
    return () => {
      if (exportPollRef.current) clearInterval(exportPollRef.current);
    };
  }, [currentExportDetail, currentExportId, fetchExports, isAuthenticated]);

  useEffect(() => {
    if (!addMappingSuccess) return;
    const timeout = setTimeout(() => setAddMappingSuccess(null), 4000);
    return () => clearTimeout(timeout);
  }, [addMappingSuccess]);

  async function handleCreateExport() {
    setExportError(null);
    setCurrentExportDetail(null);
    setIsCreatingExport(true);
    try {
      const created = await createExport({ pack_type: exportPackType });
      setCurrentExportId(created.id);
      setCurrentExportDetail({
        id: created.id,
        status: created.status,
        pack_type: exportPackType,
        created_at: created.created_at,
        started_at: null,
        completed_at: null,
        error_message: null,
      });
      await fetchExports();
    } catch (err) {
      setExportError(getErrorMessage(err));
      setCurrentExportId(null);
    } finally {
      setIsCreatingExport(false);
    }
  }

  async function handleCreateControlMapping(event: React.FormEvent) {
    event.preventDefault();
    setAddMappingError(null);
    setAddMappingSuccess(null);

    if (
      !addMappingForm.control_id.trim() ||
      !addMappingForm.framework_name.trim() ||
      !addMappingForm.framework_control_code.trim() ||
      !addMappingForm.control_title.trim() ||
      !addMappingForm.description.trim()
    ) {
      setAddMappingError('All fields are required.');
      return;
    }

    setIsAddingMapping(true);
    try {
      await createControlMapping({
        control_id: addMappingForm.control_id.trim(),
        framework_name: addMappingForm.framework_name.trim(),
        framework_control_code: addMappingForm.framework_control_code.trim(),
        control_title: addMappingForm.control_title.trim(),
        description: addMappingForm.description.trim(),
      });
      setAddMappingSuccess('Control mapping added successfully.');
      setAddMappingForm({
        control_id: '',
        framework_name: '',
        framework_control_code: '',
        control_title: '',
        description: '',
      });
      setShowAddMappingModal(false);
      await fetchControlMappings();
    } catch (err) {
      const status = typeof err === 'object' && err !== null && 'status' in err ? (err as { status: number }).status : 0;
      if (status === 409) {
        setAddMappingError('A mapping for this control ID and framework already exists.');
      } else if (status === 403) {
        setAddMappingError('Only admins can add control mappings.');
      } else {
        setAddMappingError(getErrorMessage(err));
      }
    } finally {
      setIsAddingMapping(false);
    }
  }

  return (
    <div id={panelId} role="tabpanel" tabIndex={0} className="space-y-6">
      <SettingsSectionIntro
        title="Exports & Compliance"
        description="Request audit-ready exports here and manage the control-mapping metadata used in compliance packs."
        action={<Badge variant="info">Baseline report has its own tab</Badge>}
      />

      <SettingsCard className="space-y-4">
        <div>
          <h3 className="text-base font-semibold text-text">Evidence and compliance packs</h3>
          <p className="text-sm text-muted">
            Generate an audit-ready pack for findings, actions, remediation runs, exceptions, and control-mapping context.
          </p>
        </div>

        <div className="flex flex-wrap gap-4">
          <label className="flex items-center gap-2 text-sm text-text">
            <input
              type="radio"
              name="exportPackType"
              value="evidence"
              checked={exportPackType === 'evidence'}
              onChange={() => setExportPackType('evidence')}
              className="h-4 w-4 border-border text-accent focus:ring-accent"
            />
            Evidence pack
          </label>
          <label className="flex items-center gap-2 text-sm text-text">
            <input
              type="radio"
              name="exportPackType"
              value="compliance"
              checked={exportPackType === 'compliance'}
              onChange={() => setExportPackType('compliance')}
              className="h-4 w-4 border-border text-accent focus:ring-accent"
            />
            Compliance pack
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button
            onClick={() => void handleCreateExport()}
            isLoading={isCreatingExport || Boolean(currentExportDetail && !TERMINAL_STATUSES.includes(currentExportDetail.status))}
            disabled={Boolean(currentExportDetail && !TERMINAL_STATUSES.includes(currentExportDetail.status))}
          >
            Generate {exportPackType === 'compliance' ? 'compliance' : 'evidence'} pack
          </Button>
          {currentExportDetail && TERMINAL_STATUSES.includes(currentExportDetail.status) ? (
            <Button
              variant="secondary"
              onClick={() => {
                setCurrentExportId(null);
                setCurrentExportDetail(null);
                setExportError(null);
              }}
            >
              Generate another export
            </Button>
          ) : null}
        </div>

        {exportError ? <SettingsNotice tone="danger">{exportError}</SettingsNotice> : null}

        {currentExportDetail?.status === 'success' && currentExportDetail.download_url ? (
          <SettingsNotice tone="success">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-medium">
                  {(currentExportDetail.pack_type || 'evidence') === 'compliance' ? 'Compliance' : 'Evidence'} pack ready
                </p>
                <p className="text-xs text-muted">
                  Download link expires in one hour.
                  {currentExportDetail.file_size_bytes != null ? (
                    <> Size: {(currentExportDetail.file_size_bytes / 1024).toFixed(1)} KB</>
                  ) : null}
                </p>
              </div>
              <a href={currentExportDetail.download_url} target="_blank" rel="noopener noreferrer" className="inline-flex">
                <Button variant="secondary" size="sm">
                  Download pack
                </Button>
              </a>
            </div>
          </SettingsNotice>
        ) : null}

        {currentExportDetail?.status === 'failed' ? (
          <SettingsNotice tone="danger">
            Export failed. {currentExportDetail.error_message || 'An unexpected error occurred during export generation.'}
          </SettingsNotice>
        ) : null}

        <div>
          <h4 className="mb-3 text-sm font-semibold text-text">Recent exports</h4>
          <DashboardTableCard>
            {isLoadingExports ? (
              <div className="p-6 text-center">
                <p className="animate-pulse text-muted">Loading exports...</p>
              </div>
            ) : recentExports.length === 0 ? (
              <div className="p-6 text-center">
                <p className="text-muted">No exports yet. Generate a pack above to start the audit trail.</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {recentExports.map((exp) => (
                  <div key={exp.id} className="flex items-center justify-between gap-3 p-4 transition-colors hover:bg-[var(--card-inset)]">
                    <div className="flex flex-wrap items-center gap-3">
                      <code className="rounded-full border border-[var(--badge-border)] bg-[var(--badge-bg)] px-2.5 py-1 text-xs text-[var(--badge-text)]">
                        {exp.id.slice(0, 8)}…
                      </code>
                      <Badge variant={getExportStatusBadgeVariant(exp.status)}>{exp.status}</Badge>
                      <span className="text-xs capitalize text-muted">{exp.pack_type}</span>
                      <span className="text-sm text-muted">{formatExportDate(exp.created_at)}</span>
                    </div>
                    {exp.status === 'success' ? (
                      <a
                        href="#"
                        onClick={async (event) => {
                          event.preventDefault();
                          try {
                            const detail = await getExport(exp.id);
                            if (detail.download_url) window.open(detail.download_url, '_blank', 'noopener,noreferrer');
                          } catch {
                            setExportError('Could not fetch a download link for that export.');
                          }
                        }}
                        className="text-sm font-medium text-accent hover:text-accent-hover"
                      >
                        Download
                      </a>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </DashboardTableCard>
        </div>
      </SettingsCard>

      <SettingsCard className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-base font-semibold text-text">Control mappings</h3>
            <p className="text-sm text-muted">
              Map Security Hub controls into frameworks such as SOC 2, CIS, or ISO 27001. These mappings are included
              in compliance packs.
            </p>
          </div>
          {isAdmin ? (
            <Button variant="secondary" onClick={() => {
              setShowAddMappingModal(true);
              setAddMappingError(null);
              setAddMappingSuccess(null);
            }}>
              Add mapping
            </Button>
          ) : (
            <Badge variant="info">Admins can edit mappings</Badge>
          )}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <Input
            label="Filter by control ID"
            value={controlMappingFilterControlId}
            onChange={(event) => setControlMappingFilterControlId(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                void fetchControlMappings();
              }
            }}
            placeholder="S3.1"
            className="max-w-[180px]"
          />
          <Input
            label="Filter by framework"
            value={controlMappingFilterFramework}
            onChange={(event) => setControlMappingFilterFramework(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                void fetchControlMappings();
              }
            }}
            placeholder="SOC 2"
            className="max-w-[220px]"
          />
          <Button variant="secondary" onClick={() => void fetchControlMappings()} isLoading={isLoadingControlMappings}>
            Apply filters
          </Button>
        </div>

        {controlMappingsError ? <SettingsNotice tone="danger">{controlMappingsError}</SettingsNotice> : null}
        {addMappingSuccess ? <SettingsNotice tone="success">{addMappingSuccess}</SettingsNotice> : null}

        <DashboardTableCard>
          {isLoadingControlMappings ? (
            <div className="p-6 text-center">
              <p className="animate-pulse text-muted">Loading control mappings...</p>
            </div>
          ) : controlMappings.length === 0 ? (
            <div className="p-6 text-center">
              <p className="text-muted">No control mappings match the current filters.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-[var(--card-inset)] text-left">
                    <th className="p-3 font-medium text-text">Control ID</th>
                    <th className="p-3 font-medium text-text">Framework</th>
                    <th className="p-3 font-medium text-text">Code</th>
                    <th className="p-3 font-medium text-text">Title</th>
                    <th className="p-3 font-medium text-text">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {controlMappings.map((mapping) => (
                    <tr key={mapping.id} className="border-b border-border transition-colors hover:bg-[var(--card-inset)]">
                      <td className="p-3 font-mono text-muted">{mapping.control_id}</td>
                      <td className="p-3 text-text">{mapping.framework_name}</td>
                      <td className="p-3 text-muted">{mapping.framework_control_code}</td>
                      <td className="p-3 text-text">{mapping.control_title}</td>
                      <td className="max-w-[240px] p-3 text-muted" title={mapping.description}>
                        {mapping.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DashboardTableCard>

        {controlMappingsTotal > 0 ? (
          <p className="text-xs text-muted">
            Showing {controlMappings.length} of {controlMappingsTotal} mapping(s).
          </p>
        ) : null}
      </SettingsCard>

      <Modal
        title="Add control mapping"
        isOpen={showAddMappingModal}
        onClose={() => {
          setShowAddMappingModal(false);
          setAddMappingError(null);
          setAddMappingSuccess(null);
        }}
        size="md"
      >
        <form onSubmit={handleCreateControlMapping} className="space-y-4">
          {addMappingError ? <SettingsNotice tone="danger">{addMappingError}</SettingsNotice> : null}
          <Input
            label="Control ID"
            value={addMappingForm.control_id}
            onChange={(event) => setAddMappingForm((current) => ({ ...current, control_id: event.target.value }))}
            placeholder="S3.1"
            required
          />
          <Input
            label="Framework name"
            value={addMappingForm.framework_name}
            onChange={(event) => setAddMappingForm((current) => ({ ...current, framework_name: event.target.value }))}
            placeholder="SOC 2"
            required
          />
          <Input
            label="Framework control code"
            value={addMappingForm.framework_control_code}
            onChange={(event) =>
              setAddMappingForm((current) => ({ ...current, framework_control_code: event.target.value }))
            }
            placeholder="CC6.1"
            required
          />
          <Input
            label="Control title"
            value={addMappingForm.control_title}
            onChange={(event) => setAddMappingForm((current) => ({ ...current, control_title: event.target.value }))}
            placeholder="Logical access"
            required
          />
          <Input
            label="Description"
            value={addMappingForm.description}
            onChange={(event) => setAddMappingForm((current) => ({ ...current, description: event.target.value }))}
            placeholder="Short description"
            required
          />

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setShowAddMappingModal(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isAddingMapping}>
              Add mapping
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
