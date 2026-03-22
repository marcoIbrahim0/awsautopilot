# Live E2E Run 20260320T232930Z

This folder contains the retained evidence for the notification-center live rerun and the production recovery steps that were required to complete it.

> ⚠️ Status: Targeted live rerun package. The scaffold was generated as a 35-test run, but the executed evidence in this folder focuses on the Accounts-page refresh / unified notification-center flow and the backend fixes that made it pass.

## Structure

-   00-run-metadata.md
-   00-base-issue-tracker-snapshot.md
-   wave-01 ... wave-09 with test markdown files
-   evidence/api, evidence/ui, evidence/screenshots
-   notes/

## Update Rules During Execution

1. Complete each test markdown file immediately after execution.
2. Save raw evidence into evidence folders with timestamped filenames.
3. Apply issue mapping updates in docs/live-e2e-testing/00-BASE-ISSUE-TRACKER.md after each test.
