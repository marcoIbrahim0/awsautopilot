'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Badge, getExportStatusBadgeVariant } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/contexts/AuthContext';
import {
  createBaselineReport,
  getBaselineReport,
  getBaselineReportData,
  listBaselineReports,
  type BaselineReportDetailResponse,
  type BaselineReportListItem,
  type BaselineReportViewData,
} from '@/lib/api';

const POLL_MS = 5000;
const TERMINAL = ['success', 'failed'];

const SEVERITY_STYLES: Record<string, string> = {
  CRITICAL: 'bg-red-500/10 border-red-500/30 text-red-400',
  HIGH: 'bg-orange-500/10 border-orange-500/30 text-orange-400',
  MEDIUM: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
  LOW: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
};

const SEVERITY_BADGE: Record<string, string> = {
  CRITICAL: 'bg-red-500/20 text-red-400',
  HIGH: 'bg-orange-500/20 text-orange-400',
  MEDIUM: 'bg-yellow-500/20 text-yellow-400',
  LOW: 'bg-blue-500/20 text-blue-400',
  INFORMATIONAL: 'bg-surface text-muted',
};

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
  } catch {
    return iso;
  }
}

function normalizeReadiness(readiness: string | null | undefined): string {
  if (!readiness) return 'ready';
  return readiness.replaceAll('_', ' ');
}

function CcPill({ id }: { id: string }) {
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-accent/10 text-accent border border-accent/20">
      {id}
    </span>
  );
}

function StatCard({ label, value, cls }: { label: string; value: number; cls: string }) {
  return (
    <div className={`flex-1 min-w-[100px] rounded-xl border p-4 text-center ${cls}`}>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs mt-0.5 opacity-70">{label}</p>
    </div>
  );
}

function Soc2Callout({ data }: { data: BaselineReportViewData }) {
  const { soc2_impacted_cc_ids, soc2_impacted_finding_count } = data.summary;
  if (!soc2_impacted_cc_ids?.length) return null;
  return (
    <div className="rounded-xl border border-accent/20 bg-accent/5 p-5">
      <div className="flex items-start gap-3">
        <span className="text-accent mt-0.5">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.955 11.955 0 003 10.5c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.6-.295-3.13-.831-4.529L15.75 6h.75" />
          </svg>
        </span>
        <div>
          <p className="text-sm font-semibold text-text">
            SOC 2 Readiness Snapshot
            <span className="ml-2 text-xs font-normal text-muted">
              {soc2_impacted_finding_count} of your top risks map to SOC 2 Common Criteria
            </span>
          </p>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {soc2_impacted_cc_ids.map((cc) => (
              <CcPill key={cc} id={cc} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function TopRisksTable({ risks }: { risks: BaselineReportViewData['top_risks'] }) {
  if (!risks.length) return <p className="text-sm text-muted py-4">No top risks found.</p>;
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted uppercase tracking-wide">
            <th className="px-4 py-3">Finding</th>
            <th className="px-4 py-3 whitespace-nowrap">Severity</th>
            <th className="px-4 py-3 whitespace-nowrap">Mode</th>
            <th className="px-4 py-3 whitespace-nowrap">Readiness</th>
            <th className="px-4 py-3">Account</th>
            <th className="px-4 py-3">Region</th>
            <th className="px-4 py-3 whitespace-nowrap">SOC 2 CC</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {risks.map((risk, index) => (
            <tr key={index} className="hover:bg-surface/50 transition-colors">
              <td className="px-4 py-3">
                <p className="font-medium text-text">{risk.title}</p>
                {risk.control_id && <p className="text-xs text-muted mt-0.5">{risk.control_id}</p>}
              </td>
              <td className="px-4 py-3">
                <span className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold ${SEVERITY_BADGE[risk.severity] ?? 'bg-surface text-muted'}`}>
                  {risk.severity}
                </span>
              </td>
              <td className="px-4 py-3 text-xs text-muted">{risk.recommended_mode ?? 'pr_only'}</td>
              <td className="px-4 py-3 text-xs text-muted">{normalizeReadiness(risk.remediation_readiness)}</td>
              <td className="px-4 py-3 text-muted font-mono text-xs">{risk.account_id ?? '—'}</td>
              <td className="px-4 py-3 text-muted text-xs">{risk.region ?? '—'}</td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {risk.soc2_cc_ids?.map((cc) => (
                    <CcPill key={cc} id={cc} />
                  )) ?? <span className="text-muted">—</span>}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Recommendations({ recs }: { recs: BaselineReportViewData['recommendations'] }) {
  if (!recs.length) return null;
  return (
    <ol className="space-y-3">
      {recs.map((rec, index) => (
        <li key={index} className="flex items-start gap-3 bg-surface border border-border rounded-xl p-4">
          <span className="shrink-0 w-6 h-6 rounded-full bg-accent/10 text-accent text-xs font-bold flex items-center justify-center">
            {index + 1}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-text">{rec.text}</p>
            {rec.control_id && <p className="text-xs text-muted mt-0.5">{rec.control_id}</p>}
          </div>
          {rec.soc2_cc_ids?.length ? (
            <div className="flex flex-wrap gap-1 shrink-0">
              {rec.soc2_cc_ids.map((cc) => (
                <CcPill key={cc} id={cc} />
              ))}
            </div>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

function NextActions({ actions }: { actions: BaselineReportViewData['next_actions'] }) {
  if (!actions.length) return null;
  return (
    <div className="space-y-3">
      {actions.map((item, index) => (
        <div key={`${item.action_id ?? item.title}-${index}`} className="bg-surface border border-border rounded-xl p-4">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <p className="text-sm font-semibold text-text">{item.title}</p>
              <p className="text-xs text-muted mt-0.5">
                {item.control_id ?? 'No control'} · {item.severity} · {normalizeReadiness(item.readiness)}
                {item.account_id ? ` · ${item.account_id}` : ''}
                {item.region ? ` · ${item.region}` : ''}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold ${SEVERITY_BADGE[item.severity] ?? 'bg-surface text-muted'}`}>
                {item.severity}
              </span>
              <span className="inline-flex px-2 py-0.5 rounded text-xs bg-accent/10 text-accent border border-accent/20">
                {item.recommended_mode}
              </span>
            </div>
          </div>
          <p className="text-sm text-text mt-3"><span className="font-medium">Why now:</span> {item.why_now}</p>
          <p className="text-sm text-text mt-2"><span className="font-medium">Blast radius:</span> {item.blast_radius}</p>
          <p className="text-sm text-text mt-2"><span className="font-medium">Fix path:</span> {item.fix_path}</p>
          <p className="text-xs text-muted mt-2">
            Due by: {item.due_by ? fmtDate(item.due_by) : 'Not set'}
            {item.owner ? ` · Owner: ${item.owner}` : ''}
          </p>
          {item.cta_href ? (
            <div className="mt-3">
              <a href={item.cta_href} className="text-xs font-medium text-accent hover:underline">
                {item.cta_label}
              </a>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function ChangeDelta({ delta }: { delta: BaselineReportViewData['change_delta'] }) {
  if (!delta) return null;
  return (
    <div className="bg-surface border border-border rounded-xl p-5 space-y-2">
      {delta.compared_to_report_at && (
        <p className="text-xs text-muted">Compared to: {fmtDate(delta.compared_to_report_at)}</p>
      )}
      <div className="flex flex-wrap gap-3">
        <span className="text-sm text-text">New open: <strong>{delta.new_open_count}</strong></span>
        <span className="text-sm text-text">Regressed: <strong>{delta.regressed_count}</strong></span>
        <span className="text-sm text-text">Stale open: <strong>{delta.stale_open_count}</strong></span>
        <span className="text-sm text-text">Closed: <strong>{delta.closed_count}</strong></span>
      </div>
      <p className="text-sm text-text">{delta.summary}</p>
    </div>
  );
}

function ConfidenceGaps({ gaps }: { gaps: BaselineReportViewData['confidence_gaps'] }) {
  if (!gaps.length) return null;
  return (
    <div className="space-y-2">
      {gaps.map((gap) => (
        <div key={gap.category} className="bg-surface border border-border rounded-xl p-4">
          <p className="text-sm font-semibold text-text">
            {gap.category.replaceAll('_', ' ')} · {gap.count}
          </p>
          <p className="text-sm text-text mt-1">{gap.detail}</p>
          {gap.affected_control_ids?.length ? (
            <p className="text-xs text-muted mt-2">Affected controls: {gap.affected_control_ids.join(', ')}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function ClosureProof({ items }: { items: BaselineReportViewData['closure_proof'] }) {
  if (!items.length) return null;
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={`${item.finding_id}-${item.action_id ?? 'na'}`} className="bg-surface border border-border rounded-xl p-4">
          <p className="text-sm font-semibold text-text">{item.title}</p>
          <p className="text-xs text-muted mt-0.5">
            {item.finding_id}
            {item.control_id ? ` · ${item.control_id}` : ''}
            {item.account_id ? ` · ${item.account_id}` : ''}
            {item.region ? ` · ${item.region}` : ''}
          </p>
          <p className="text-sm text-text mt-2">{item.evidence_note}</p>
          <p className="text-xs text-muted mt-1">
            Resolved: {item.resolved_at ? fmtDate(item.resolved_at) : 'n/a'}
            {item.remediation_run_id ? ` · Run: ${item.remediation_run_id.slice(0, 8)}…` : ''}
          </p>
        </div>
      ))}
    </div>
  );
}

type ReportSectionKey =
  | 'overview'
  | 'next-actions'
  | 'top-risks'
  | 'change-delta'
  | 'confidence-gaps'
  | 'closure-proof'
  | 'recommendations';

type ReportSection = {
  key: ReportSectionKey;
  label: string;
};

function ReportView({ data }: { data: BaselineReportViewData }) {
  const summary = data.summary;
  const sections = useMemo<ReportSection[]>(() => {
    const base: ReportSection[] = [{ key: 'overview', label: 'Overview' }];
    if (data.next_actions.length > 0) base.push({ key: 'next-actions', label: 'Next Actions' });
    if (data.top_risks.length > 0) base.push({ key: 'top-risks', label: 'Top Risks' });
    if (data.change_delta) base.push({ key: 'change-delta', label: 'Change Since Last Baseline' });
    if (data.confidence_gaps.length > 0) base.push({ key: 'confidence-gaps', label: 'Confidence Gaps' });
    if (data.closure_proof.length > 0) base.push({ key: 'closure-proof', label: 'Closure Proof' });
    if (data.recommendations.length > 0) base.push({ key: 'recommendations', label: 'Recommendations' });
    return base;
  }, [data]);
  const [activeSection, setActiveSection] = useState<ReportSectionKey>('overview');
  const visibleSection = sections.some((item) => item.key === activeSection)
    ? activeSection
    : (sections[0]?.key ?? 'overview');

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3">
        <StatCard label="Total" value={summary.total_finding_count} cls="bg-surface border-border text-text" />
        <StatCard label="Open" value={summary.open_count} cls="bg-surface border-border text-text" />
        <StatCard label="Critical" value={summary.critical_count} cls={SEVERITY_STYLES.CRITICAL} />
        <StatCard label="High" value={summary.high_count} cls={SEVERITY_STYLES.HIGH} />
        <StatCard label="Medium" value={summary.medium_count} cls={SEVERITY_STYLES.MEDIUM} />
        <StatCard label="Low" value={summary.low_count} cls={SEVERITY_STYLES.LOW} />
        <StatCard label="Resolved" value={summary.resolved_count} cls="bg-surface border-border text-text" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-3">
          <div className="bg-surface border border-border rounded-xl p-4 lg:sticky lg:top-4">
            <p className="text-xs font-medium text-muted uppercase tracking-wide mb-3">Report Navigation</p>
            <div className="space-y-1">
              {sections.map((section) => (
                <button
                  key={section.key}
                  type="button"
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    visibleSection === section.key
                      ? 'bg-accent/10 text-accent border border-accent/20'
                      : 'text-muted hover:text-text hover:bg-bg/60 border border-transparent'
                  }`}
                  onClick={() => setActiveSection(section.key)}
                >
                  {section.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="lg:col-span-9 space-y-6">
          {visibleSection === 'overview' && (
            <>
              <section>
                <h2 className="text-base font-semibold text-text mb-3">Overview</h2>
                <div className="bg-surface border border-border rounded-xl p-5">
                  <p className="text-sm text-text leading-relaxed">{summary.narrative}</p>
                  <p className="text-xs text-muted mt-2">
                    Report date: {summary.report_date}
                    {summary.account_count != null && ` · ${summary.account_count} account${summary.account_count !== 1 ? 's' : ''}`}
                    {summary.region_count != null && ` · ${summary.region_count} region${summary.region_count !== 1 ? 's' : ''}`}
                  </p>
                </div>
              </section>
              <Soc2Callout data={data} />
            </>
          )}
          {visibleSection === 'next-actions' && (
            <section>
              <h2 className="text-base font-semibold text-text mb-3">Next Actions</h2>
              <NextActions actions={data.next_actions} />
            </section>
          )}
          {visibleSection === 'top-risks' && (
            <section>
              <h2 className="text-base font-semibold text-text mb-3">Top Risks</h2>
              <TopRisksTable risks={data.top_risks} />
            </section>
          )}
          {visibleSection === 'change-delta' && data.change_delta && (
            <section>
              <h2 className="text-base font-semibold text-text mb-3">Change Since Last Baseline</h2>
              <ChangeDelta delta={data.change_delta} />
            </section>
          )}
          {visibleSection === 'confidence-gaps' && (
            <section>
              <h2 className="text-base font-semibold text-text mb-3">Confidence Gaps</h2>
              <ConfidenceGaps gaps={data.confidence_gaps} />
            </section>
          )}
          {visibleSection === 'closure-proof' && (
            <section>
              <h2 className="text-base font-semibold text-text mb-3">Closure Proof</h2>
              <ClosureProof items={data.closure_proof} />
            </section>
          )}
          {visibleSection === 'recommendations' && (
            <section>
              <h2 className="text-base font-semibold text-text mb-3">Recommendations</h2>
              <Recommendations recs={data.recommendations} />
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function ReportHistoryList({
  history,
  selectedId,
  onSelect,
}: {
  history: BaselineReportListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (!history.length) return null;
  return (
    <section>
      <h2 className="text-sm font-semibold text-text mb-3">Report history</h2>
      <div className="bg-surface border border-border rounded-xl overflow-hidden divide-y divide-border">
        {history.map((item) => (
          <div
            key={item.id}
            className={`flex items-center justify-between p-4 transition-colors hover:bg-bg/50 cursor-pointer ${selectedId === item.id ? 'bg-accent/5 border-l-2 border-accent' : ''}`}
            onClick={() => onSelect(item.id)}
          >
            <div className="flex items-center gap-3">
              <code className="text-xs font-mono text-muted bg-bg px-2 py-1 rounded border border-border">{item.id.slice(0, 8)}…</code>
              <Badge variant={getExportStatusBadgeVariant(item.status)}>{item.status}</Badge>
              <span className="text-sm text-muted">{fmtDate(item.requested_at)}</span>
            </div>
            {item.status === 'success' && (
              <span className="text-sm font-medium text-accent">
                {selectedId === item.id ? 'Viewing' : 'View'}
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

export function BaselineReportPanel() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [history, setHistory] = useState<BaselineReportListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<BaselineReportDetailResponse | null>(null);
  const [viewData, setViewData] = useState<BaselineReportViewData | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchHistory = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const { items } = await listBaselineReports({ limit: 10 });
      setHistory(items);
      const latest = items.find((item) => item.status === 'success') ?? items[0] ?? null;
      if (latest && !selectedId) setSelectedId(latest.id);
    } catch {
      setHistory([]);
    }
  }, [isAuthenticated, selectedId]);

  const loadReportData = useCallback(async (id: string) => {
    setLoadingData(true);
    setError(null);
    setViewData(null);
    try {
      const data = await getBaselineReportData(id);
      setViewData(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Could not load report data.';
      setError(message);
    } finally {
      setLoadingData(false);
    }
  }, []);

  const pollDetail = useCallback(async (id: string) => {
    try {
      const current = await getBaselineReport(id);
      setDetail(current);
      if (current.status === 'success') {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        loadReportData(id);
        fetchHistory();
      } else if (current.status === 'failed') {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        setError(current.outcome ?? 'Report generation failed.');
        fetchHistory();
      }
    } catch {
      // ignore poll errors
    }
  }, [loadReportData, fetchHistory]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  useEffect(() => {
    if (!selectedId) return;

    getBaselineReport(selectedId)
      .then((current) => {
        setDetail(current);
        if (current.status === 'success') {
          loadReportData(selectedId);
        } else if (!TERMINAL.includes(current.status)) {
          pollRef.current = setInterval(() => pollDetail(selectedId), POLL_MS);
        }
      })
      .catch(() => {
        // ignore initial load errors
      });

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [selectedId, loadReportData, pollDetail]);

  const handleRequest = async () => {
    setRequesting(true);
    setError(null);
    try {
      const created = await createBaselineReport();
      setSelectedId(created.id);
      setDetail({
        id: created.id,
        status: created.status,
        requested_at: created.requested_at,
        completed_at: null,
        file_size_bytes: null,
        download_url: null,
        outcome: null,
      });
      fetchHistory();
    } catch (err: unknown) {
      const response = err as { status?: number };
      if (response?.status === 429) {
        setError('One report per 24 hours. Please try again later.');
      } else {
        setError(err instanceof Error ? err.message : 'Request failed.');
      }
    } finally {
      setRequesting(false);
    }
  };

  if (!authLoading && !isAuthenticated) {
    return (
      <div className="bg-surface border border-border rounded-xl p-8 text-center">
        <p className="text-muted mb-4">Please sign in to view your report.</p>
        <Button onClick={() => { window.location.href = '/login'; }} variant="primary">Sign In</Button>
      </div>
    );
  }

  const isPending = detail && !TERMINAL.includes(detail.status);
  const isFailed = detail?.status === 'failed';
  const noReports = !authLoading && history.length === 0 && !detail;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-text">Baseline Security Report</h1>
          {detail?.requested_at && (
            <p className="text-sm text-muted mt-0.5">
              {viewData?.tenant_name && <span className="font-medium text-text">{viewData.tenant_name} · </span>}
              {viewData?.summary.report_date ?? fmtDate(detail.requested_at)}
            </p>
          )}
        </div>
        <Button onClick={handleRequest} variant="primary" disabled={requesting || Boolean(isPending)}>
          {requesting ? (
            <>
              <span className="inline-block w-4 h-4 border-2 border-bg border-t-transparent rounded-full animate-spin mr-2" />
              Requesting…
            </>
          ) : (
            <>
              <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              Request new report
            </>
          )}
        </Button>
      </div>

      {isPending && (
        <div className="bg-surface border border-border rounded-xl p-8 flex flex-col items-center gap-3 text-center">
          <span className="w-10 h-10 border-4 border-accent border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-medium text-text">Generating your report…</p>
          <p className="text-xs text-muted">This usually takes a few minutes. The page updates automatically.</p>
        </div>
      )}

      {(error || isFailed) && (
        <div className="p-4 bg-danger/10 border border-danger/20 rounded-xl">
          <p className="text-sm font-medium text-danger">Report failed</p>
          <p className="text-sm text-muted mt-1">{error ?? detail?.outcome ?? 'An error occurred.'}</p>
        </div>
      )}

      {noReports && !isPending && !error && (
        <div className="bg-surface border border-border rounded-xl p-12 flex flex-col items-center gap-4 text-center">
          <svg className="w-12 h-12 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-text font-semibold">No baseline report yet</p>
          <p className="text-sm text-muted max-w-sm">
            Request your first report to get a full security baseline with SOC 2 readiness insights.
          </p>
          <Button onClick={handleRequest} variant="primary" disabled={requesting}>
            Request baseline report
          </Button>
        </div>
      )}

      {loadingData && (
        <div className="bg-surface border border-border rounded-xl p-8 text-center">
          <p className="text-muted animate-pulse text-sm">Loading report…</p>
        </div>
      )}

      {viewData && !loadingData && <ReportView data={viewData} />}

      <ReportHistoryList
        history={history}
        selectedId={selectedId}
        onSelect={(id) => {
          setSelectedId(id);
          setViewData(null);
          setError(null);
        }}
      />
    </div>
  );
}
