# Tenant Isolation

The product trust story is not only IAM. Reviewers also need proof that the SaaS does not leak cross-tenant data on API and artifact surfaces.

## Evidence Map

| Surface | Proof |
|---|---|
| Evidence pack S3 export paths | [tests/test_evidence_export_s3.py](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_evidence_export_s3.py) |
| Grouped remediation route boundaries | [Wave 5 post-archive wrong-tenant checks](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T133714Z-rem-profile-wave5-post-archive-rerun/tests/rpw5-post-archive-04.md) |
| Shared grouped-run / resend boundaries | [Wave 4 tenant-isolation rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260314T193034Z-rem-profile-wave4-e2e/tests/rpw4-12.md) |
| Archived grouped execution and run detail boundaries | [Wave 6 live closure checks](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T175132Z-rem-profile-wave6-live-aws-e2e/tests/w6-live-11.md) |

## What These Prove

- Wrong-tenant read attempts on action groups and remediation runs return `404` or empty scoped collections rather than foreign rows.
- No-auth and invalid-token probes on bundle ZIP and grouped callback/reporting surfaces remain deny-closed.
- S3 export keys are tenant-prefixed and the export service rejects spoofed tenant access.

## Current Scope Note

These isolation proofs remain relevant even though customer `WriteRole` and `direct_fix` are out of scope. The active trust claim is still a multi-tenant SaaS control plane generating tenant-scoped PR bundles and evidence artifacts, so API and storage isolation remain mandatory.
