# Phase 3 P2 Live Validation Run Metadata

- Timestamp (UTC): `2026-03-12T14:31:38Z`
- Frontend URL: `https://ocypheris.com`
- API URL: `https://api.ocypheris.com`
- Operator identity used: `marco.ibrahim@ocypheris.com`
- Scope tested:
  - `P2.1` Trusted threat-intelligence weighting
  - `P2.2` Threat-intel decay and provenance transparency
- Notes:
  - This run uses a fresh browser context for UI validation.
  - `P2` validation requires live findings/actions that already carry threat-intel evidence; no production mutations will be introduced solely to fabricate candidates.
  - Auth path used in this run:
    - Fresh browser session reached authenticated `https://ocypheris.com/findings` after same-operator token-based session injection.
    - Read-only API evidence capture reused the same operator bearer token so the live requests remained authenticated and repeatable.
