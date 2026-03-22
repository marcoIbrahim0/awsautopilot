# AssumeRole Evidence

The current trust package uses two proof layers:

1. fresh sanitized SaaS-account CloudTrail showing successful `AssumeRole` calls into the customer `SecurityAutopilotReadRole`
2. authoritative customer-side retained evidence from the March 20, 2026 live closure rerun

## Fresh SaaS-Side Proof

The generated buyer package contains two sanitized successful `AssumeRole` events on March 20, 2026 UTC+02 from the live API Lambda execution role into `arn:aws:iam::696505809372:role/SecurityAutopilotReadRole`.

- [Sanitized CloudTrail AssumeRole events](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/evidence/aws/cloudtrail-assumerole-sanitized.json)

These extracts intentionally omit temporary credentials, access keys, and raw event blobs. Older raw CloudTrail exports in historical live-run folders are not the reviewer-safe source of truth anymore.

## Customer-Side Authoritative Source

- [Issue 2 live closure summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun/notes/final-summary.md)
- [Redacted live ReadRole document](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/evidence/aws/authoritative-live-read-role-redacted.json)
- [Redacted live stack summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/evidence/aws/authoritative-live-stack-summary.json)
- [Issue 2 API closure summary](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun/evidence/api/issue2-closure-api-summary.json)

## Why The Package Mixes Fresh And Retained Evidence

The customer-side live closure package from March 20, 2026 remains the authoritative retained proof for the validated connected account. The new buyer package adds fresh, sanitized SaaS-side CloudTrail proof and fresh Access Analyzer validation of the current repo templates without reusing older raw evidence dumps that contained unnecessary sensitive fields.
