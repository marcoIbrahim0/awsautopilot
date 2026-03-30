import { AppShell } from '@/components/layout';
import { ButtonLink } from '@/components/ui/ButtonLink';
import { ExportsComplianceTab } from '@/app/settings/ExportsComplianceTab';
import { buildSettingsTabHref } from '@/app/settings/settings-tabs';

export default function ExportsPage() {
  return (
    <AppShell title="Exports">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-text">Exports</h1>
            <p className="text-sm text-muted">
              Generate evidence packs, review recent exports, and manage compliance control mappings from the main exports workspace.
            </p>
          </div>
          <ButtonLink href={buildSettingsTabHref('baseline-report')} variant="secondary">
            Open baseline report
          </ButtonLink>
        </div>

        <ExportsComplianceTab panelId="exports-panel" />
      </div>
    </AppShell>
  );
}
