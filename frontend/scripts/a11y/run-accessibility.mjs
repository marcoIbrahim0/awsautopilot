#!/usr/bin/env node

import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';

const BASE_URL = process.env.A11Y_BASE_URL ?? 'http://127.0.0.1:3000';
const OUTPUT_DIR = path.resolve(process.cwd(), process.env.A11Y_OUTPUT_DIR ?? 'a11y-results');
const WCAG_TAGS = ['wcag2a', 'wcag2aa'];

const THRESHOLDS = {
  critical: parseThreshold('A11Y_MAX_CRITICAL', 0),
  serious: parseThreshold('A11Y_MAX_SERIOUS', 0),
  moderate: parseThreshold('A11Y_MAX_MODERATE', 2),
  minor: parseThreshold('A11Y_MAX_MINOR', 10),
};

const FLOWS = [
  { id: 'onboarding', name: 'Onboarding', path: '/onboarding', onboardingComplete: false },
  { id: 'settings', name: 'Settings', path: '/settings?tab=team', onboardingComplete: true },
  { id: 'findings', name: 'Findings', path: '/findings', onboardingComplete: true },
];

const SAMPLE_ACCOUNT = {
  id: 'acc_001',
  account_id: '123456789012',
  role_read_arn: 'arn:aws:iam::123456789012:role/SecurityAutopilotReadRole',
  role_write_arn: 'arn:aws:iam::123456789012:role/SecurityAutopilotWriteRole',
  regions: ['us-east-1', 'us-west-2'],
  status: 'validated',
  last_validated_at: '2026-02-17T18:00:00Z',
  created_at: '2026-02-17T18:00:00Z',
  updated_at: '2026-02-17T18:00:00Z',
};

const SAMPLE_FINDING = {
  id: 'finding_001',
  finding_id: 'arn:aws:securityhub:us-east-1:123456789012:control/default/Finding/abc',
  tenant_id: 'tenant_001',
  account_id: SAMPLE_ACCOUNT.account_id,
  region: 'us-east-1',
  severity_label: 'HIGH',
  severity_normalized: 70,
  status: 'NEW',
  in_scope: true,
  title: 'S3 bucket should block public access',
  description: 'Sample finding used for accessibility baseline scans.',
  resource_id: 'arn:aws:s3:::example-bucket',
  resource_type: 'AwsS3Bucket',
  control_id: 'S3.1',
  standard_name: 'AWS Foundational Security Best Practices',
  first_observed_at: '2026-02-17T18:00:00Z',
  last_observed_at: '2026-02-17T18:00:00Z',
  updated_at: '2026-02-17T18:00:00Z',
  created_at: '2026-02-17T18:00:00Z',
  updated_at_db: '2026-02-17T18:00:00Z',
  source: 'security_hub',
};

function parseThreshold(name, fallback) {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function buildAuthPayload(onboardingComplete) {
  return {
    user: {
      id: 'user_001',
      email: 'admin@example.com',
      name: 'Security Admin',
      role: 'admin',
      onboarding_completed_at: onboardingComplete ? '2026-02-17T18:00:00Z' : null,
    },
    tenant: {
      id: 'tenant_001',
      name: 'Demo Tenant',
      external_id: 'external-tenant-001',
    },
    saas_account_id: '111122223333',
    read_role_launch_stack_url:
      'https://us-east-1.console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review',
    read_role_template_url: 'https://example.com/security-autopilot-read-role-v1.4.1.yaml',
    read_role_region: 'us-east-1',
    read_role_default_stack_name: 'SecurityAutopilotReadRole',
    write_role_launch_stack_url:
      'https://us-east-1.console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review',
    write_role_template_url: 'https://example.com/security-autopilot-write-role-v1.4.1.yaml',
    write_role_default_stack_name: 'SecurityAutopilotWriteRole',
    control_plane_token: 'mock-control-plane-token',
    control_plane_token_fingerprint: 'abcd1234',
    control_plane_token_created_at: '2026-02-17T18:00:00Z',
    control_plane_token_revoked_at: null,
    control_plane_token_active: true,
    control_plane_forwarder_template_url:
      'https://example.com/security-autopilot-control-plane-forwarder-v1.0.0.yaml',
    control_plane_ingest_url: 'https://api.security-autopilot.example.com/api/control-plane/intake',
    control_plane_forwarder_default_stack_name: 'SecurityAutopilotControlPlaneForwarder',
  };
}

async function respondJson(route, status, body) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function setupApiMocks(page, flow) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const method = request.method().toUpperCase();
    const url = new URL(request.url());
    const { pathname } = url;

    if (pathname === '/api/auth/me' && method === 'GET') {
      await respondJson(route, 200, buildAuthPayload(flow.onboardingComplete));
      return;
    }

    if (pathname === '/api/users' && method === 'GET') {
      await respondJson(route, 200, [
        {
          id: 'user_001',
          email: 'admin@example.com',
          name: 'Security Admin',
          role: 'admin',
          created_at: '2026-02-17T18:00:00Z',
        },
      ]);
      return;
    }

    if (pathname === '/api/aws/accounts' && method === 'GET') {
      await respondJson(route, 200, flow.id === 'onboarding' ? [] : [SAMPLE_ACCOUNT]);
      return;
    }

    if (pathname === '/api/meta/scope' && method === 'GET') {
      await respondJson(route, 200, {
        only_in_scope_controls: false,
        in_scope_controls_count: 0,
        disabled_sources: [],
      });
      return;
    }

    if (pathname === '/api/findings' && method === 'GET') {
      await respondJson(route, 200, {
        items: flow.id === 'findings' ? [SAMPLE_FINDING] : [],
        total: flow.id === 'findings' ? 1 : 0,
      });
      return;
    }

    if (pathname === '/api/actions' && method === 'GET') {
      await respondJson(route, 200, { items: [], total: 0 });
      return;
    }

    if (pathname === '/api/exports' && method === 'GET') {
      await respondJson(route, 200, { items: [], total: 0 });
      return;
    }

    if (pathname === '/api/control-mappings' && method === 'GET') {
      await respondJson(route, 200, { items: [], total: 0 });
      return;
    }

    if (pathname === '/api/baseline-report' && method === 'GET') {
      await respondJson(route, 200, { items: [], total: 0 });
      return;
    }

    if (pathname === '/api/users/me/digest-settings' && method === 'GET') {
      await respondJson(route, 200, {
        digest_enabled: true,
        digest_recipients: 'admin@example.com',
      });
      return;
    }

    if (pathname === '/api/users/me/slack-settings' && method === 'GET') {
      await respondJson(route, 200, {
        slack_webhook_configured: false,
        slack_digest_enabled: false,
      });
      return;
    }

    if (pathname.includes('/ingest') && method === 'POST') {
      await respondJson(route, 200, {
        account_id: SAMPLE_ACCOUNT.account_id,
        jobs_queued: 1,
        regions: SAMPLE_ACCOUNT.regions,
        message_ids: ['msg_001'],
        message: 'Mock ingest queued.',
      });
      return;
    }

    if (pathname === '/api/actions/compute' && method === 'POST') {
      await respondJson(route, 200, {
        account_id: SAMPLE_ACCOUNT.account_id,
        message_id: 'msg_compute_001',
        status: 'queued',
      });
      return;
    }

    if (pathname.endsWith('/service-readiness') && method === 'POST') {
      await respondJson(route, 200, {
        account_id: SAMPLE_ACCOUNT.account_id,
        overall_ready: true,
        all_security_hub_enabled: true,
        all_aws_config_enabled: true,
        all_access_analyzer_enabled: true,
        all_inspector_enabled: true,
        missing_security_hub_regions: [],
        missing_aws_config_regions: [],
        missing_access_analyzer_regions: [],
        missing_inspector_regions: [],
        regions: [],
      });
      return;
    }

    if (pathname.endsWith('/control-plane-readiness') && method === 'GET') {
      await respondJson(route, 200, {
        account_id: SAMPLE_ACCOUNT.account_id,
        stale_after_minutes: 30,
        overall_ready: true,
        missing_regions: [],
        regions: [],
      });
      return;
    }

    if (pathname === '/api/auth/logout' && method === 'POST') {
      await respondJson(route, 200, { ok: true });
      return;
    }

    await respondJson(route, 200, {});
  });
}

function createImpactCounts() {
  return { critical: 0, serious: 0, moderate: 0, minor: 0 };
}

function computeImpactCounts(violations) {
  const counts = createImpactCounts();
  for (const violation of violations) {
    const impact = violation.impact ?? 'minor';
    const nodeCount = Array.isArray(violation.nodes) ? violation.nodes.length : 1;
    if (Object.hasOwn(counts, impact)) {
      counts[impact] += nodeCount;
    }
  }
  return counts;
}

function exceedsThreshold(counts) {
  return (
    counts.critical > THRESHOLDS.critical ||
    counts.serious > THRESHOLDS.serious ||
    counts.moderate > THRESHOLDS.moderate ||
    counts.minor > THRESHOLDS.minor
  );
}

async function analyzeFlow(browser, flow) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1024 },
    colorScheme: 'dark',
  });
  const page = await context.newPage();
  await setupApiMocks(page, flow);

  await page.goto(new URL(flow.path, BASE_URL).toString(), { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(750);

  const result = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  const impactCounts = computeImpactCounts(result.violations);
  const failing = exceedsThreshold(impactCounts);

  const topViolations = result.violations.map((violation) => ({
    id: violation.id,
    impact: violation.impact ?? 'minor',
    help: violation.help,
    helpUrl: violation.helpUrl,
    nodes: violation.nodes.length,
  }));

  await page.screenshot({
    path: path.join(OUTPUT_DIR, `${flow.id}.png`),
    fullPage: true,
  });

  await fs.writeFile(
    path.join(OUTPUT_DIR, `${flow.id}.axe.json`),
    JSON.stringify(result, null, 2),
    'utf8'
  );

  await context.close();

  return {
    id: flow.id,
    name: flow.name,
    path: flow.path,
    impactCounts,
    violations: result.violations.length,
    passes: result.passes.length,
    incomplete: result.incomplete.length,
    inapplicable: result.inapplicable.length,
    failing,
    topViolations,
  };
}

async function writeSummary(results) {
  const summary = {
    generated_at: new Date().toISOString(),
    base_url: BASE_URL,
    thresholds: THRESHOLDS,
    flows: results,
    failing_flows: results.filter((flow) => flow.failing).map((flow) => flow.id),
  };

  const lines = [
    '# Accessibility Baseline Summary',
    '',
    `Generated at: ${summary.generated_at}`,
    `Base URL: ${summary.base_url}`,
    '',
    '## Failure thresholds (max impacted nodes)',
    '',
    `- critical: ${THRESHOLDS.critical}`,
    `- serious: ${THRESHOLDS.serious}`,
    `- moderate: ${THRESHOLDS.moderate}`,
    `- minor: ${THRESHOLDS.minor}`,
    '',
    '## Flow results',
    '',
    '| Flow | Critical | Serious | Moderate | Minor | Rule Violations | Status |',
    '| --- | ---: | ---: | ---: | ---: | ---: | --- |',
    ...results.map((flow) => {
      const status = flow.failing ? 'FAIL' : 'PASS';
      return `| ${flow.name} (${flow.path}) | ${flow.impactCounts.critical} | ${flow.impactCounts.serious} | ${flow.impactCounts.moderate} | ${flow.impactCounts.minor} | ${flow.violations} | ${status} |`;
    }),
    '',
    '## Top violations',
    '',
  ];

  for (const flow of results) {
    lines.push(`### ${flow.name}`);
    if (flow.topViolations.length === 0) {
      lines.push('- none');
      lines.push('');
      continue;
    }
    for (const violation of flow.topViolations.slice(0, 10)) {
      lines.push(
        `- [${violation.impact}] \`${violation.id}\` (${violation.nodes} nodes): ${violation.help} (${violation.helpUrl})`
      );
    }
    lines.push('');
  }

  await fs.writeFile(path.join(OUTPUT_DIR, 'summary.json'), JSON.stringify(summary, null, 2), 'utf8');
  await fs.writeFile(path.join(OUTPUT_DIR, 'summary.md'), `${lines.join('\n').trim()}\n`, 'utf8');
  return summary;
}

async function main() {
  await fs.rm(OUTPUT_DIR, { recursive: true, force: true });
  await fs.mkdir(OUTPUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  try {
    const results = [];
    for (const flow of FLOWS) {
      const flowResult = await analyzeFlow(browser, flow);
      results.push(flowResult);
      console.log(
        `${flowResult.name}: critical=${flowResult.impactCounts.critical}, serious=${flowResult.impactCounts.serious}, moderate=${flowResult.impactCounts.moderate}, minor=${flowResult.impactCounts.minor}, violations=${flowResult.violations}`
      );
    }
    const summary = await writeSummary(results);
    if (summary.failing_flows.length > 0) {
      console.error(`Accessibility thresholds exceeded in: ${summary.failing_flows.join(', ')}`);
      process.exit(1);
    }
    console.log('Accessibility thresholds satisfied for all flows.');
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error('Accessibility scan failed:', error);
  process.exit(1);
});
