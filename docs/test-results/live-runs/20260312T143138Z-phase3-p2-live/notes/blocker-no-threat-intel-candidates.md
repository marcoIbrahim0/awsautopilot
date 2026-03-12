# Blocker: No Live Threat-Intel Candidates

## Observed blocker

The current production tenant/account does not contain any live finding or action that is suitable for Phase 3 P2 validation.

Observed live dataset:
- `7` findings
- `6` actions
- all findings are Security Hub configuration/control findings
- no finding title/control pair suggests a CVE-bearing or Inspector-style vulnerability record
- no inspected action detail exposes any of the P2 threat-intel fields or provenance fields

Direct evidence of the missing P2 contract:
- `../evidence/api/04-actions.body.json`
- `../evidence/api/action-442e46ac.body.json`
- `../evidence/api/action-e6b1eac2.body.json`
- `../evidence/api/action-caf5dc54.body.json`
- `../evidence/api/action-3301b44c.body.json`
- `../evidence/api/action-0ca64b94.body.json`
- `../evidence/api/action-0b8c765a.body.json`

## Exact AWS-side scenarios needed

At least these live scenarios are required before P2 can be fully validated:

1. A vulnerability-bearing finding/action with trusted threat-intel evidence:
   - CVE or vulnerability context present in the live finding payload
   - trusted source `cisa_kev` or `high_confidence_exploitability`
   - confidence high enough to pass the source floor
   - timestamp recent enough to produce non-zero applied points

2. A comparable vulnerability-bearing finding/action without trusted threat-intel boost:
   - similar risk/vulnerability context
   - no trusted threat signal applied
   - needed for side-by-side weighting/order comparison

3. An older trusted signal for decay/provenance:
   - trusted signal timestamp old enough that decay reduces contribution below base contribution
   - ideally one fully aged-out signal so zero-point provenance remains visible

4. Optional fail-closed fixtures if you want direct live proof beyond the main positive path:
   - untrusted source
   - `trusted=false`
   - confidence below the source floor
   - inactive/non-exploitable `high_confidence_exploitability`
   - malformed threat-intel payload
   - no exploit-factor headroom remaining

## Whether AWS Console work is required now

`YES`

The current live tenant does not already surface the required vulnerability/threat-intel scenarios. Someone must create or surface them on the AWS side now, or use an existing AWS-side automation path that results in those findings landing in Security Hub/Inspector for account `696505809372`.
