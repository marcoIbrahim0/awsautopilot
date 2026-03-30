'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { Badge, getSeverityBadgeVariant } from '@/components/ui/Badge';
import { TenantIdForm } from '@/components/TenantIdForm';
import { getFindings, Finding, getErrorMessage } from '@/lib/api';
import { useTenantId } from '@/lib/tenant';
import { useAuth } from '@/contexts/AuthContext';
import { getSourceLabel, getSourceShortLabel } from '@/lib/source';
import { SourceTabs } from '@/app/findings/SourceTabs';

type TimeFilter = 'week' | 'month' | 'all';

// ---------------------------------------------------------------------------
// E1 — Actionable Risk Score widget
// ---------------------------------------------------------------------------

const MAX_SCORE = 100;
const CRITICAL_WEIGHT = 10;
const HIGH_WEIGHT = 4;

function computeRiskScore(critical: number, high: number): number {
  const raw = critical * CRITICAL_WEIGHT + high * HIGH_WEIGHT;
  return Math.min(MAX_SCORE, raw);
}

function getRiskLabel(score: number): { label: string; color: string } {
  if (score === 0) return { label: 'No active risk', color: 'text-success' };
  if (score <= 20) return { label: 'Low risk', color: 'text-success' };
  if (score <= 50) return { label: 'Moderate risk', color: 'text-warning' };
  if (score <= 80) return { label: 'High risk', color: 'text-orange-400' };
  return { label: 'Critical risk', color: 'text-danger' };
}

function getRingColor(score: number): string {
  if (score === 0) return '#22c55e';   // success green
  if (score <= 20) return '#22c55e';
  if (score <= 50) return '#f59e0b';   // warning amber
  if (score <= 80) return '#fb923c';   // orange
  return '#ef4444';                    // danger red
}

interface ActionableRiskScoreProps {
  criticalCount: number;
  highCount: number;
}

function ActionableRiskScore({ criticalCount, highCount }: ActionableRiskScoreProps) {
  const score = computeRiskScore(criticalCount, highCount);
  const { label, color } = getRiskLabel(score);
  const ringColor = getRingColor(score);

  // SVG arc: r=40, circumference=2πr≈251.3
  const radius = 40;
  const circ = 2 * Math.PI * radius;
  const dashOffset = circ * (1 - score / MAX_SCORE);

  return (
    <div className="mb-6 p-6 rounded-[2rem] nm-neu-lg border-none flex flex-col sm:flex-row items-center gap-6">
      {/* Arc ring */}
      <div className="relative shrink-0 w-28 h-28">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          {/* Track */}
          <circle
            cx="50" cy="50" r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="10"
            className="text-border/50"
          />
          {/* Progress */}
          <circle
            cx="50" cy="50" r={radius}
            fill="none"
            stroke={ringColor}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={dashOffset}
            style={{ transition: 'stroke-dashoffset 0.6s ease, stroke 0.4s ease' }}
          />
        </svg>
        {/* Score number */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-text leading-none">{score}</span>
          <span className="text-xs text-muted">/ {MAX_SCORE}</span>
        </div>
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted uppercase tracking-wide font-medium mb-1">Actionable Risk Score</p>
        <p className={`text-lg font-semibold mb-2 ${color}`}>{label}</p>
        <p className="text-sm text-muted leading-relaxed">
          Based on <strong className="text-text">{criticalCount} critical</strong> and{' '}
          <strong className="text-text">{highCount} high</strong> in-scope findings requiring action.
          Score = Critical × {CRITICAL_WEIGHT} + High × {HIGH_WEIGHT}, capped at {MAX_SCORE}.
        </p>
      </div>

      {/* Severity breakdown */}
      <div className="flex sm:flex-col gap-4 sm:gap-2 shrink-0 text-center sm:text-right">
        <div>
          <p className="text-2xl font-bold text-danger leading-none">{criticalCount}</p>
          <p className="text-xs text-muted">Critical</p>
        </div>
        <div className="w-px sm:w-auto sm:h-px bg-border" />
        <div>
          <p className="text-2xl font-bold text-warning leading-none">{highCount}</p>
          <p className="text-xs text-muted">High</p>
        </div>
      </div>
    </div>
  );
}


export default function TopRisksPage() {
  const { tenantId, setTenantId } = useTenantId();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [findings, setFindings] = useState<Finding[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('all');
  const [sourceFilter, setSourceFilter] = useState<string>('');
  const effectiveTenantId = isAuthenticated ? undefined : tenantId;
  const showContent = isAuthenticated || tenantId;

  // Calculate time cutoff based on selected filter
  const getTimeCutoff = useCallback((filter: TimeFilter): string | undefined => {
    const now = new Date();
    switch (filter) {
      case 'week': {
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        return weekAgo.toISOString();
      }
      case 'month': {
        const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        return monthAgo.toISOString();
      }
      case 'all':
      default:
        return undefined;
    }
  }, []);

  const fetchTopRisks = useCallback(async () => {
    if (!showContent) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Calculate time cutoff for the selected filter
      const firstObservedSince = getTimeCutoff(timeFilter);

      // Fetch critical and high severity findings (Step 2B.4: optional source filter)
      const response = await getFindings(
        {
          severity: 'CRITICAL,HIGH',
          status: 'NEW,NOTIFIED',
          first_observed_since: firstObservedSince,
          ...(sourceFilter ? { source: sourceFilter } : {}),
          limit: 20,
          offset: 0,
        },
        effectiveTenantId
      );
      setFindings(response.items);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [showContent, timeFilter, sourceFilter, getTimeCutoff, effectiveTenantId]);

  useEffect(() => {
    fetchTopRisks();
  }, [fetchTopRisks, timeFilter]);

  // Group findings by severity for stats
  const criticalCount = findings.filter((f) => f.severity_label === 'CRITICAL').length;
  const highCount = findings.filter((f) => f.severity_label === 'HIGH').length;

  // Get top 6 for bento grid
  const topFindings = findings.slice(0, 6);

  return (
    <AppShell title="Top Risks">
      <div className="max-w-6xl mx-auto w-full">
        {!showContent && !authLoading && isAuthenticated && (
          <TenantIdForm onSave={setTenantId} />
        )}

        {showContent && (
          <>
            {/* ============================================================ */}
            {/* E1 — Actionable Risk Score widget                            */}
            {/* ============================================================ */}
            {!isLoading && !error && (
              <ActionableRiskScore criticalCount={criticalCount} highCount={highCount} />
            )}

            {/* Header with stats */}
            <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
              <div className="flex flex-wrap items-center gap-4">
                {/* Time filter tabs */}
                <div className="flex items-center gap-1 p-1 nm-neu-pressed rounded-2xl overflow-x-auto no-scrollbar max-w-full">
                  {[
                    { value: 'week' as const, label: 'This Week' },
                    { value: 'month' as const, label: '30 Days' },
                    { value: 'all' as const, label: 'All Time' },
                  ].map((tab) => (
                    <button
                      key={tab.value}
                      onClick={() => setTimeFilter(tab.value)}
                      className={`
                    px-4 py-2 text-sm font-semibold rounded-xl shrink-0
                    transition-all duration-300 tracking-tight
                    ${timeFilter === tab.value
                          ? 'nm-neu-sm text-accent'
                          : 'text-muted hover:text-text hover:nm-neu-sm'
                        }
                  `}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Source filter (Step 2B.4) */}
                <SourceTabs selected={sourceFilter} onChange={setSourceFilter} />
              </div>

              {/* Stats */}
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-2xl font-bold text-danger">{criticalCount}</p>
                  <p className="text-xs text-muted">Critical</p>
                </div>
                <div className="w-px h-8 bg-border" />
                <div className="text-right">
                  <p className="text-2xl font-bold text-warning">{highCount}</p>
                  <p className="text-xs text-muted">High</p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={fetchTopRisks}
                  disabled={isLoading}
                  className="h-10 px-4 shrink-0 whitespace-nowrap"
                  leftIcon={
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                    </svg>
                  }
                >
                  Refresh
                </Button>
              </div>
            </div>

            {/* Error state (API errors only) */}
            {showContent && error && (
              <div className="mb-6 p-5 rounded-2xl nm-neu-flat border border-danger/20 bg-danger/5">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-danger mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                  </svg>
                  <div>
                    <p className="text-sm font-medium text-danger">Failed to load top risks</p>
                    <p className="text-sm text-danger/80">{error}</p>
                  </div>
                </div>
                <Button variant="secondary" size="sm" onClick={fetchTopRisks} className="mt-3">
                  Retry
                </Button>
              </div>
            )}

            {/* Loading state */}
            {isLoading && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div
                    key={i}
                    className={`rounded-2xl nm-neu-sm border-none p-6 animate-pulse ${i === 1 ? 'md:col-span-2 lg:col-span-2 lg:row-span-2' : ''
                      }`}
                  >
                    <div className="h-6 bg-border rounded w-3/4 mb-3" />
                    <div className="h-4 bg-border rounded w-full mb-2" />
                    <div className="h-4 bg-border rounded w-2/3" />
                  </div>
                ))}
              </div>
            )}

            {/* Empty state */}
            {!isLoading && !error && findings.length === 0 && (
              <div className="text-center py-12 rounded-[2rem] nm-neu-lg border-none">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-success/10 flex items-center justify-center">
                  <svg className="w-8 h-8 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-text mb-2">No critical or high risks</h3>
                <p className="text-muted mb-4 max-w-md mx-auto">
                  Great news! There are no critical or high severity findings requiring immediate attention.
                </p>
                <Link href="/findings">
                  <Button variant="secondary">View All Findings</Button>
                </Link>
              </div>
            )}

            {/* Bento grid */}
            {!isLoading && !error && topFindings.length > 0 && (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
                  {topFindings.map((finding, index) => (
                    <Link
                      key={finding.id}
                      href={`/findings/${finding.id}`}
                      className={`
                    group rounded-2xl nm-neu-sm border-none p-6
                    transition-all duration-300 hover:nm-neu-lg
                    ${index === 0 ? 'md:col-span-2 lg:col-span-2 lg:row-span-2' : ''}
                  `}
                    >
                      {/* Rank badge and source/severity */}
                      <div className="flex items-start justify-between mb-4">
                        <span
                          className={`
                        inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold
                        ${index === 0
                              ? 'bg-accent text-bg'
                              : 'bg-bg text-muted'
                            }
                      `}
                        >
                          #{index + 1}
                        </span>
                        <div className="flex items-center gap-2">
                          {finding.source && (
                            <Badge
                              variant="default"
                              title={`Source: ${getSourceLabel(finding.source)}`}
                              className="font-mono text-xs"
                            >
                              {getSourceShortLabel(finding.source)}
                            </Badge>
                          )}
                          <Badge variant={getSeverityBadgeVariant(finding.severity_label)}>
                            {finding.severity_label}
                          </Badge>
                        </div>
                      </div>

                      {/* Title */}
                      <h3
                        className={`font-semibold text-text mb-3 group-hover:text-accent transition-colors ${index === 0 ? 'text-lg' : 'text-base'
                          }`}
                      >
                        {finding.title}
                      </h3>

                      {/* Control ID */}
                      {finding.control_id && (
                        <p className="text-xs text-accent font-mono mb-2">{finding.control_id}</p>
                      )}

                      {/* Description (only for #1) */}
                      {index === 0 && finding.description && (
                        <p className="text-sm text-muted mb-4 line-clamp-3">
                          {finding.description}
                        </p>
                      )}

                      {/* Resource */}
                      {finding.resource_id && (
                        <p
                          className="text-xs text-muted font-mono truncate mb-3"
                          title={finding.resource_id}
                        >
                          {finding.resource_id}
                        </p>
                      )}

                      {/* Footer */}
                      <div className="flex items-center gap-3 text-xs text-muted pt-3 border-t border-border">
                        <span className="font-mono">{finding.account_id}</span>
                        <span>•</span>
                        <span>{finding.region}</span>
                      </div>
                    </Link>
                  ))}
                </div>

                {/* View all link */}
                {findings.length > 6 && (
                  <div className="text-center">
                    <Link href="/findings?severity=CRITICAL,HIGH&status=NEW,NOTIFIED">
                      <Button variant="secondary">
                        View All {findings.length} High-Priority Findings
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                        </svg>
                      </Button>
                    </Link>
                  </div>
                )}

                <div className="mt-8 p-6 sm:p-8 rounded-[2rem] nm-neu-lg border-none">
                  <h2 className="text-xl font-bold tracking-tight text-text mb-6">Quick Actions</h2>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                    <Link
                      href="/findings?severity=CRITICAL"
                      className="p-5 rounded-2xl nm-neu-pressed border-none hover:nm-neu-sm transition-all duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-danger/10 rounded-xl">
                          <svg className="w-5 h-5 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                          </svg>
                        </div>
                        <div>
                          <p className="font-medium text-text">Critical Findings</p>
                          <p className="text-sm text-muted">View all critical issues</p>
                        </div>
                      </div>
                    </Link>

                    <Link
                      href="/accounts"
                      className="p-5 rounded-2xl nm-neu-pressed border-none hover:nm-neu-sm transition-all duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-accent/10 rounded-xl">
                          <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
                          </svg>
                        </div>
                        <div>
                          <p className="font-medium text-text">Refresh Findings</p>
                          <p className="text-sm text-muted">Trigger new ingestion</p>
                        </div>
                      </div>
                    </Link>

                    <Link
                      href="/findings?status=RESOLVED"
                      className="p-5 rounded-2xl nm-neu-pressed border-none hover:nm-neu-sm transition-all duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-success/10 rounded-xl">
                          <svg className="w-5 h-5 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        </div>
                        <div>
                          <p className="font-medium text-text">Resolved Findings</p>
                          <p className="text-sm text-muted">View fixed issues</p>
                        </div>
                      </div>
                    </Link>
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
