'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useAuth } from '@/contexts/AuthContext';
import {
  ActionsFilters,
  FindingsFilters,
  SaasActionItem,
  SaasBaselineReportItem,
  SaasExportItem,
  SaasFindingItem,
  SaasRemediationRunItem,
  SaasTenantAccount,
  SaasTenantOverview,
  SaasTenantUser,
  SupportFile,
  SupportNote,
  createSupportNote,
  getErrorMessage,
  getSaasSupportFiles,
  getSaasTenantAccounts,
  getSaasTenantActions,
  getSaasTenantBaselineReports,
  getSaasTenantExports,
  getSaasTenantFindings,
  getSaasTenantOverview,
  getSaasTenantRemediationRuns,
  getSaasTenantUsers,
  getSupportNotes,
  uploadSupportFileDirect,
} from '@/lib/api';
import { startNavigationFeedback } from '@/lib/navigation-feedback';

export const runtime = 'nodejs';

type TabKey = 'overview' | 'users' | 'accounts' | 'findings' | 'actions' | 'runs' | 'exports' | 'notes' | 'files';

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'users', label: 'Users' },
  { key: 'accounts', label: 'Accounts' },
  { key: 'findings', label: 'Findings' },
  { key: 'actions', label: 'Actions' },
  { key: 'runs', label: 'Runs' },
  { key: 'exports', label: 'Exports' },
  { key: 'notes', label: 'Notes' },
  { key: 'files', label: 'Files' },
];

export default function AdminTenantDetailPage() {
  const params = useParams<{ tenantId: string }>();
  const tenantId = params?.tenantId;
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();

  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [overview, setOverview] = useState<SaasTenantOverview | null>(null);
  const [users, setUsers] = useState<SaasTenantUser[]>([]);
  const [accounts, setAccounts] = useState<SaasTenantAccount[]>([]);
  const [findings, setFindings] = useState<SaasFindingItem[]>([]);
  const [actions, setActions] = useState<SaasActionItem[]>([]);
  const [runs, setRuns] = useState<SaasRemediationRunItem[]>([]);
  const [exports, setExports] = useState<SaasExportItem[]>([]);
  const [baselineReports, setBaselineReports] = useState<SaasBaselineReportItem[]>([]);
  const [notes, setNotes] = useState<SupportNote[]>([]);
  const [files, setFiles] = useState<SupportFile[]>([]);
  const [newNote, setNewNote] = useState('');
  const [newFile, setNewFile] = useState<File | null>(null);
  const [fileMessage, setFileMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const findingsFilters: FindingsFilters = useMemo(() => ({ limit: 100, offset: 0 }), []);
  const actionsFilters: ActionsFilters = useMemo(() => ({ limit: 100, offset: 0 }), []);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.replace('/login');
      return;
    }
    if (!user?.is_saas_admin) {
      router.replace('/accounts');
      return;
    }
    if (!tenantId) return;
    let active = true;
    Promise.all([
      getSaasTenantOverview(tenantId),
      getSaasTenantUsers(tenantId),
      getSaasTenantAccounts(tenantId),
      getSaasTenantFindings(tenantId, findingsFilters),
      getSaasTenantActions(tenantId, actionsFilters),
      getSaasTenantRemediationRuns(tenantId),
      getSaasTenantExports(tenantId),
      getSaasTenantBaselineReports(tenantId),
      getSupportNotes(tenantId),
      getSaasSupportFiles(tenantId),
    ])
      .then(([overviewData, usersData, accountsData, findingsData, actionsData, runsData, exportsData, baselinesData, notesData, filesData]) => {
        if (!active) return;
        setOverview(overviewData);
        setUsers(usersData);
        setAccounts(accountsData);
        setFindings(findingsData.items);
        setActions(actionsData.items);
        setRuns(runsData.items);
        setExports(exportsData);
        setBaselineReports(baselinesData);
        setNotes(notesData);
        setFiles(filesData);
      })
      .catch((err) => {
        if (!active) return;
        setError(getErrorMessage(err));
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading, isAuthenticated, user, tenantId, router, findingsFilters, actionsFilters]);

  async function onCreateNote() {
    if (!tenantId || !newNote.trim()) return;
    const note = await createSupportNote(tenantId, { body: newNote.trim() });
    setNotes((prev) => [note, ...prev]);
    setNewNote('');
  }

  async function onUploadFile() {
    if (!tenantId || !newFile) return;
    const uploaded = await uploadSupportFileDirect(tenantId, newFile, fileMessage || undefined, true);
    setFiles((prev) => [uploaded, ...prev]);
    setNewFile(null);
    setFileMessage('');
  }

  function renderTabContent() {
    if (isLoading) return <p className="text-muted">Loading…</p>;
    if (error) return <p className="text-danger">{error}</p>;
    switch (activeTab) {
      case 'overview':
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-surface border border-border rounded-xl p-4">
              <p className="text-sm text-muted">Findings by severity</p>
              <pre className="text-xs mt-2 whitespace-pre-wrap">{JSON.stringify(overview?.findings_by_severity ?? {}, null, 2)}</pre>
            </div>
            <div className="bg-surface border border-border rounded-xl p-4">
              <p className="text-sm text-muted">Findings trend</p>
              <pre className="text-xs mt-2 whitespace-pre-wrap">{JSON.stringify(overview?.findings_trend ?? {}, null, 2)}</pre>
            </div>
            <div className="bg-surface border border-border rounded-xl p-4">
              <p className="text-sm text-muted">Actions by status</p>
              <pre className="text-xs mt-2 whitespace-pre-wrap">{JSON.stringify(overview?.actions_by_status ?? {}, null, 2)}</pre>
            </div>
            <div className="bg-surface border border-border rounded-xl p-4">
              <p className="text-sm text-muted">Accounts by status</p>
              <pre className="text-xs mt-2 whitespace-pre-wrap">{JSON.stringify(overview?.accounts_by_status ?? {}, null, 2)}</pre>
            </div>
          </div>
        );
      case 'users':
        return <ListTable columns={['Name', 'Email', 'Role', 'Created']} rows={users.map((u) => [u.name, u.email, u.role, new Date(u.created_at).toLocaleString()])} />;
      case 'accounts':
        return <ListTable columns={['Account', 'Regions', 'Status', 'Last Validated']} rows={accounts.map((a) => [a.account_id, a.regions.join(', '), a.status, a.last_validated_at ? new Date(a.last_validated_at).toLocaleString() : '—'])} />;
      case 'findings':
        return <ListTable columns={['Severity', 'Status', 'Account', 'Region', 'Title']} rows={findings.map((f) => [f.severity_label, f.status, f.account_id, f.region, f.title])} />;
      case 'actions':
        return <ListTable columns={['Priority', 'Status', 'Account', 'Region', 'Title']} rows={actions.map((a) => [String(a.priority), a.status, a.account_id, a.region ?? '—', a.title])} />;
      case 'runs':
        return <ListTable columns={['Mode', 'Status', 'Approved By', 'Created', 'Outcome']} rows={runs.map((r) => [r.mode, r.status, r.approved_by_email ?? '—', new Date(r.created_at).toLocaleString(), r.outcome ?? '—'])} />;
      case 'exports':
        return (
          <div className="space-y-6">
            <ListTable columns={['Type', 'Status', 'Created', 'Completed', 'Size']} rows={exports.map((e) => [e.pack_type, e.status, new Date(e.created_at).toLocaleString(), e.completed_at ? new Date(e.completed_at).toLocaleString() : '—', e.file_size_bytes ? `${e.file_size_bytes} bytes` : '—'])} />
            <ListTable columns={['Baseline Status', 'Requested', 'Completed', 'Outcome']} rows={baselineReports.map((b) => [b.status, new Date(b.requested_at).toLocaleString(), b.completed_at ? new Date(b.completed_at).toLocaleString() : '—', b.outcome ?? '—'])} />
          </div>
        );
      case 'notes':
        return (
          <div className="space-y-4">
            <div className="flex gap-2">
              <Input value={newNote} onChange={(e) => setNewNote(e.target.value)} placeholder="Add internal support note" />
              <Button onClick={() => onCreateNote().catch((err) => setError(getErrorMessage(err)))}>Add Note</Button>
            </div>
            <ListTable columns={['Author', 'Created', 'Note']} rows={notes.map((n) => [n.created_by_email ?? '—', new Date(n.created_at).toLocaleString(), n.body])} />
          </div>
        );
      case 'files':
        return (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2 items-center">
              <input
                type="file"
                onChange={(e) => setNewFile(e.target.files?.[0] ?? null)}
                className="text-sm"
              />
              <Input
                value={fileMessage}
                onChange={(e) => setFileMessage(e.target.value)}
                placeholder="Optional message"
                className="max-w-sm"
              />
              <Button onClick={() => onUploadFile().catch((err) => setError(getErrorMessage(err)))} disabled={!newFile}>
                Upload
              </Button>
            </div>
            <ListTable columns={['Filename', 'Status', 'Size', 'Uploaded', 'Message']} rows={files.map((f) => [f.filename, f.status ?? 'available', f.size_bytes ? `${f.size_bytes} bytes` : '—', f.uploaded_at ? new Date(f.uploaded_at).toLocaleString() : '—', f.message ?? '—'])} />
          </div>
        );
      default:
        return null;
    }
  }

  return (
    <AppShell title={`Tenant: ${overview?.tenant_name ?? tenantId}`}>
      <div className="max-w-7xl mx-auto w-full space-y-4">
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              startNavigationFeedback();
              router.push('/admin/tenants');
            }}
          >
            Back
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              startNavigationFeedback();
              router.push(`/admin/control-plane/${tenantId}`);
            }}
          >
            Control Plane
          </Button>
          {TABS.map((tab) => (
            <Button
              key={tab.key}
              variant={activeTab === tab.key ? 'primary' : 'secondary'}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </Button>
          ))}
        </div>
        {renderTabContent()}
      </div>
    </AppShell>
  );
}

function ListTable({ columns, rows }: { columns: string[]; rows: string[][] }) {
  return (
    <div className="bg-surface border border-border rounded-xl overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-bg/50 border-b border-border">
          <tr>
            {columns.map((column) => (
              <th key={column} className="text-left px-4 py-3">{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td className="px-4 py-3 text-muted" colSpan={columns.length}>No data.</td>
            </tr>
          )}
          {rows.map((row, idx) => (
            <tr key={`${idx}-${row[0] ?? 'row'}`} className="border-b border-border/60">
              {row.map((value, valueIdx) => (
                <td key={`${idx}-${valueIdx}`} className="px-4 py-3">{value}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
