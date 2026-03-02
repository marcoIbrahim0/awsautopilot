You are a senior engineering lead, cloud security architect, and QA strategist 
with deep experience shipping B2B SaaS products to production. You are doing a 
full production-readiness review of this project.

You have no prior context about this codebase. Start fresh. Read everything 
before forming any opinion.

---

PHASE 1 — FULL PROJECT DISCOVERY

Read the entire project at /Users/marcomaher/AWS Security Autopilot including:

- All frontend source files
- All backend source files
- All infrastructure definitions
- All configuration files (environment, CI/CD, deployment)
- All documentation files
- All test files (unit, integration, e2e — if any exist)
- All dependency manifests (package.json, requirements.txt, etc.)
- All existing audit or review documents in /docs

Do not skim. Read every directory. Build a complete mental model of:
- What this product does and who it is for
- How the frontend, backend, and AWS integrations connect
- What the data model looks like
- How authentication and authorization work
- How the product is currently deployed
- What testing infrastructure currently exists
- What monitoring and observability infrastructure currently exists

Once discovery is complete, produce a one-page product summary confirming 
your understanding before proceeding. Stop and wait for confirmation 
that your understanding is correct before moving to Phase 2.

---

PHASE 2 — PRODUCTION READINESS AUDIT

Review the project across every dimension below. For each dimension, 
report findings tied to specific files, components, or infrastructure 
definitions — no generalizations.

SECTION 1 — SECURITY HARDENING
- Authentication: are sessions, tokens, and refresh flows secure?
- Authorization: is every API endpoint and page gated correctly by role?
- Secrets management: are any secrets hardcoded, in env files, or in source?
- Input validation: is user input validated and sanitized server-side?
- Dependency vulnerabilities: are any dependencies outdated or known-vulnerable?
- CORS, CSP, and security headers: are they configured correctly?
- Rate limiting: is it applied to auth endpoints and sensitive API routes?
- Multi-tenancy isolation: can one tenant ever access another tenant's data?

SECTION 2 — RELIABILITY AND RESILIENCE
- What happens when the AWS scanner fails or times out?
- What happens when a remediation job fails mid-execution?
- Are there retry mechanisms for failed jobs?
- Are there circuit breakers or graceful degradation patterns?
- Is there a queue or job system — and is it durable?
- What is the behavior under high load or concurrent remediation runs?

SECTION 3 — DATA INTEGRITY
- Are database migrations safe to run on a live system?
- Is there any risk of data loss if a job crashes mid-write?
- Are transactions used where multiple writes must be atomic?
- Is there a backup and restore strategy?

SECTION 4 — OBSERVABILITY
- Is structured logging implemented across backend services?
- Are errors captured with enough context to debug production issues?
- Is there application-level metrics collection (latency, job success rate, etc.)?
- Is there alerting on critical failure conditions?
- Is there distributed tracing across service boundaries?

SECTION 5 — DEPLOYMENT AND INFRASTRUCTURE
- Is the deployment process automated and repeatable?
- Is there a staging environment that mirrors production?
- Are environment-specific configs properly separated?
- Is infrastructure defined as code and version controlled?
- Are there rollback procedures for failed deployments?
- Is the deployment zero-downtime capable?

SECTION 6 — FRONTEND PRODUCTION READINESS
- Are there runtime error boundaries that prevent full app crashes?
- Is there client-side error tracking?
- Are environment variables correctly scoped (no secrets exposed to browser)?
- Is the build optimized (bundle size, code splitting, image optimization)?
- Is there a CDN in front of static assets?

SECTION 7 — COMPLIANCE AND AUDIT TRAIL
- Are all user actions that modify data logged with actor, timestamp, and change?
- Are remediation actions logged immutably for compliance reporting?
- Is there an audit log accessible to tenant admins?
- Is data retention policy implemented?

SECTION 8 — OPERATIONAL READINESS
- Is there a runbook for common operational tasks?
- Is there an on-call process or escalation path defined?
- Are there health check endpoints for every service?
- Is there a defined SLA and are there mechanisms to measure against it?

SECTION 9 — MISSING FEATURES FOR GA
- Based on the codebase, what features appear partially implemented?
- What flows have no error handling?
- What user journeys have no empty or loading states?
- What settings or configuration options are referenced but not yet built?

SECTION 10 — BACKEND COMPLETENESS
- Is every API endpoint the frontend calls actually implemented in the backend?
- Are there any frontend features that call endpoints that return stubs, 
  hardcoded responses, or TODOs?
- Are background jobs, workers, and scheduled tasks fully implemented 
  or partially stubbed?
- Are all third-party integrations (Slack, GitHub, etc.) fully wired end-to-end 
  or only partially connected?
- Flag every place where the backend is not yet production-ready to support 
  a feature the frontend already exposes to the operator

---

PHASE 3 — END-TO-END TESTING STRATEGY

The goal of end-to-end testing for this product is to verify the complete 
operator experience from the user's perspective — meaning a real operator 
can sign up, connect their AWS account, see real findings, run real 
remediations, and confirm real resolution without encountering broken flows, 
missing states, unclear errors, or dead ends.

Every layer of testing below must be evaluated from this lens: 
does it confirm the product works end-to-end for the operator, 
not just that individual functions return correct values.

LAYER 1 — UNIT TESTS
- Which modules, functions, and components most need unit test coverage?
- What is currently untested that carries the highest risk?
- Recommend a framework and pattern consistent with the existing stack.

LAYER 2 — INTEGRATION TESTS
- Which service boundaries need integration tests?
- Which database operations need integration tests?
- Which AWS API interactions need mocking and testing?

LAYER 3 — END-TO-END OPERATOR WORKFLOW TESTS

Map every critical operator workflow as a user-perspective test scenario. 
For each scenario define:
- Who the actor is (new operator, existing operator, admin, SaaS admin)
- The starting state (clean account, partially onboarded, fully onboarded, etc.)
- Every step the operator takes including navigation, clicks, and form input
- The expected system response at each step (UI state, backend job triggered, 
  AWS API called, notification sent)
- The final confirmed end state that proves the workflow succeeded
- What a broken backend would look like at each step so failures are detectable

The mandatory scenarios to cover are:

  SCENARIO 1 — New operator onboarding
  From landing page through account creation, AWS account connection, 
  role setup, first scan completion, and landing on a populated findings dashboard.
  Every step must work against a real backend — no mocks for this scenario.

  SCENARIO 2 — Finding triage and direct remediation
  From findings dashboard, identify the highest severity finding, understand 
  what is wrong, initiate a direct-fix remediation, monitor the run to completion, 
  trigger recompute, and confirm the finding is resolved. 
  Verify the finding status updates correctly across all relevant pages.

  SCENARIO 3 — PR bundle remediation
  From findings or actions, identify a pr-bundle action, select actions for 
  bundling, generate the PR bundle, confirm the bundle is created, simulate 
  PR approval, and verify the expected finding state change.

  SCENARIO 4 — Multi-account posture review
  Operator with multiple connected AWS accounts reviews overall security posture, 
  filters findings by account, understands per-account severity breakdown, 
  and navigates to account-specific remediation.

  SCENARIO 5 — Team collaboration
  Admin invites a team member, team member accepts invite and logs in, 
  team member views findings and initiates a remediation, admin reviews 
  the team member's actions in audit or history views.

  SCENARIO 6 — Notification and alerting
  Operator configures Slack webhook, a new critical finding is detected, 
  Slack notification fires correctly, operator navigates from Slack notification 
  to the specific finding in the product.

  SCENARIO 7 — Evidence export
  Operator requests an evidence export, export job completes, operator downloads 
  and verifies the export contains the expected findings and metadata.

  SCENARIO 8 — Full resolution campaign
  From initial scan through triage, remediation across multiple findings, 
  recompute, and a final campaign summary showing resolved vs outstanding findings.

For each scenario also document:
- Which backend endpoints are exercised
- Which AWS APIs are called
- Which background jobs must complete
- What the operator sees if any single component in the chain fails
- How the operator recovers from that failure

LAYER 4 — LIVE AWS ENVIRONMENT TESTS

--- BEGIN EXISTING TEST PLAN ---

You are an AWS solutions architect and cloud security specialist. You have no 
knowledge of any specific security SaaS product or its remediation logic. 
Your only job is to design and deploy vulnerable AWS architectures that serve 
as realistic test targets.

Before designing anything, you must first discover exactly which AWS security 
controls and action types this product covers by reading the codebase. Do not 
assume, do not use general AWS security knowledge to fill gaps, and do not 
proceed to architecture design until the discovery phase is complete and confirmed.

PHASE 1 — DISCOVER COVERED CONTROLS AND ACTIONS

Search the project codebase at /Users/marcomaher/AWS Security Autopilot for any 
file that defines or enumerates security controls, rules, checks, or findings 
the product implements, any file that defines action types specifically which 
actions are direct-fix and which are pr-bundle, and any enum constant config 
file or registry that lists control IDs rule IDs or action IDs explicitly. 
Read every relevant file. Extract only what is explicitly defined in code. 
Produce the confirmed control and action inventory tables and stop for 
confirmation before proceeding.

PHASE 2 — ARCHITECTURE DESIGN

Design two medium-complexity AWS architectures that collectively cover every 
confirmed control and action type, represent believable real-world business 
scenarios, use at least 5 distinct AWS service categories each, have 
interconnected components, are 2-4 tiers with 8-15 resources per architecture, 
and contain naturally embedded misconfigurations.

Include for each architecture: narrative, resource map, misconfiguration 
inventory cross-referenced to confirmed control IDs, negative test resources 
(correctly configured resources of the same types to verify no false positives), 
and isolation into three groups: Group A detection resources, Group B negative 
test resources, Group C remediation verification resources, tagged 
TestGroup=detection, TestGroup=negative, TestGroup=remediation respectively.

Provide reset commands per vulnerable resource to return it to its original 
misconfigured state after remediation without full teardown. Provide three 
teardown scripts: Group A only, Group B only, and full teardown in reverse 
dependency order.

All deployment scripts must use AWS CLI v2 only, parameterize ACCOUNT_ID and 
AWS_REGION, start with aws sts get-caller-identity, include a prominent account 
isolation warning block requiring the operator to type CONFIRM before proceeding, 
comment every command, use --no-cli-pager, tag every resource 
Environment=security-test and ManagedBy=test-script, and prefer t3.micro 
and db.t3.micro sizing.

PHASE 3 — ADVERSARIAL TEST CASES FOR ARCHITECTURE DESIGN

When designing the two architectures in Phase 2, you must embed the following 
specific adversarial scenarios into the resource configurations. These are not 
additional architectures — they are specific resource designs within the two 
architectures that are constructed to stress-test three critical product behaviors. 
Design each resource to be realistic enough that the scenario arises naturally, 
not as an obvious trap.

ADVERSARIAL SCENARIO A — BLAST RADIUS PRE-VALIDATION

Goal: Force the product to encounter resources where the naive remediation 
would cause a production outage, so you can verify it detects the risk 
before generating a PR.

For each architecture, include at least one resource from each of the 
following blast radius patterns:

  A1 — S3 bucket with active static website hosting AND public access enabled
  The bucket must have:
  - Static website hosting enabled (IndexDocument and ErrorDocument configured)
  - A bucket policy granting s3:GetObject to "*"
  - Public access block disabled
  - At least one object in the bucket (upload a placeholder index.html)
  - No CloudFront distribution in front of it
  The naive remediation (enable public access block) would immediately take 
  down a live website. The product must detect website hosting is active 
  and flag this as high-risk before generating any PR.
  Tag this resource: BlastRadiusTest=website-hosting

  A2 — Security group that is actively referenced by other resources
  Create a security group with 0.0.0.0/0 inbound on port 22 that is:
  - Attached to a running EC2 instance
  - Also referenced as the source in at least one other security group's 
    inbound rule (create a second security group that allows inbound from 
    the first security group's ID)
  - Also used as the security group for an RDS instance
  The naive remediation (delete the rule or replace the security group) would 
  break the RDS inbound rule and potentially the EC2 instance connectivity. 
  The product must enumerate all dependent resources before proposing a change.
  Tag this resource: BlastRadiusTest=sg-dependency-chain

  A3 — IAM role with an overly broad policy that is actively assumed by 
  multiple services
  Create an IAM role with a wildcard policy (Action: "*", Resource: "*") 
  that is referenced in:
  - An EC2 instance profile (attached to a running instance)
  - A Lambda function execution role (create a placeholder Lambda)
  - A trust policy that allows both ec2.amazonaws.com and lambda.amazonaws.com
  The naive remediation (scope down the policy) would break one or both 
  services if the scoped policy does not include all actions they actually 
  use. The product must identify all principals assuming the role before 
  proposing a scoped replacement.
  Tag this resource: BlastRadiusTest=iam-multi-principal

For each A-series resource, document in the misconfiguration inventory:
- What the naive remediation would do
- What the correct blast-radius-aware remediation should do instead
- What signal in the AWS API the product should use to detect the risk
  (e.g. GetBucketWebsite, DescribeNetworkInterfaces, ListEntitiesForPolicy)

ADVERSARIAL SCENARIO B — CONTEXTUAL AWARENESS: STATE VS CODE

Goal: Force the product to encounter existing infrastructure that already 
has partial configuration, so you can verify that generated IaC appends 
to existing state rather than replacing it.

For each architecture, include at least one resource from each of the 
following contextual complexity patterns:

  B1 — S3 bucket with an existing complex bucket policy
  Create a bucket with:
  - A multi-statement bucket policy already in place containing at minimum:
    * One statement granting cross-account read access to a specific 
      account ID (use a fake but realistic account ID: 123456789012)
    * One statement granting s3:PutObject to a specific IAM role ARN
    * One statement with a Condition block (e.g. aws:SourceVpc condition)
  - Public access block disabled (the misconfiguration to remediate)
  The product must generate Terraform that enables public access block 
  WITHOUT replacing or overwriting the existing bucket policy. 
  A terraform plan against this bucket must show zero policy changes 
  and only the public access block change.
  Tag this resource: ContextTest=existing-complex-policy

  B2 — VPC security group with mixed legitimate and overly-permissive rules
  Create a security group with:
  - Three legitimate, specific inbound rules (port 443 from a specific CIDR, 
    port 5432 from a specific security group ID, port 8080 from a specific IP)
  - One overly-permissive rule (port 22 from 0.0.0.0/0) that is the 
    misconfiguration to remediate
  The product must generate a change that removes only the 0.0.0.0/0 rule 
  without touching the three legitimate rules. A terraform plan must show 
  exactly one rule removal and zero changes to the other three rules.
  Tag this resource: ContextTest=mixed-sg-rules

  B3 — IAM role with a mix of necessary managed policies and an overly 
  permissive inline policy
  Create an IAM role with:
  - Two AWS managed policies attached (e.g. AmazonS3ReadOnlyAccess, 
    AmazonEC2ReadOnlyAccess) — these are legitimate and must be preserved
  - One custom inline policy with Action: "*", Resource: "*" — this is 
    the misconfiguration to remediate
  The product must generate a change that removes or scopes the inline policy 
  only, without detaching the managed policies. A terraform plan must show 
  zero changes to managed policy attachments.
  Tag this resource: ContextTest=inline-plus-managed

For each B-series resource, document in the misconfiguration inventory:
- The existing legitimate configuration that must be preserved
- The specific misconfiguration to remediate
- What a destructive (incorrect) terraform plan would show 
  (unexpected resource destruction or replacement)
- What a correct terraform plan would show (targeted single change only)

ADVERSARIAL SCENARIO C — DRY-RUN PROOF VALIDATION

Goal: Verify that the product's generated PR description contains enough 
information for an engineer to trust and approve the change without 
additional investigation.

For each architecture, designate exactly two resources as PR proof 
validation targets — one from Scenario A and one from Scenario B above. 
These are the resources against which you will validate the PR description 
quality after the product generates a PR bundle.

For each PR proof validation target, document the following expected PR 
description elements that the product must include. When you deploy the 
architectures and run the product against them, verify each element 
is present in the generated PR:

  C1 — Change scope statement
  The PR description must state explicitly how many resources will be 
  modified, created, or destroyed. Acceptable format:
  "This change modifies 1 resource and creates 0 new resources. 
   No resources will be destroyed."
  Flag as FAILING if the PR description does not include an explicit 
  resource count.

  C2 — Conflict validation statement
  The PR description must confirm that the generated Terraform was 
  validated against the current AWS state. Acceptable format:
  "Validated against current AWS state on [date]. No conflicts detected 
   with existing configuration."
  Flag as FAILING if the PR description does not include a validation 
  timestamp or conflict check result.

  C3 — Traffic impact statement
  For any resource that is network-facing (security groups, S3 public access, 
  load balancers, CloudFront), the PR description must include a statement 
  about active traffic impact. Acceptable format:
  "This change does not affect active traffic" OR 
  "WARNING: This change may affect active traffic. See blast radius assessment."
  Flag as FAILING if the PR description omits a traffic impact statement 
  for a network-facing resource.

  C4 — Rollback command
  The PR description must include a specific rollback command the engineer 
  can run if the change causes issues. Acceptable format:
  "Rollback: terraform apply -target=[resource_type].[resource_name] 
   with the previous state file."
  Flag as FAILING if no rollback command is present.

  C5 — Preserved configuration confirmation
  For any B-series resource (contextual awareness targets), the PR description 
  must explicitly confirm what existing configuration was preserved. 
  Acceptable format:
  "Existing bucket policy with [N] statements preserved unchanged. 
   Only public access block setting modified."
  Flag as FAILING if the PR does not confirm what was preserved 
  for a resource with pre-existing configuration.

Document the C-series validation as a checklist in the coverage matrix:
| Resource | C1 Scope | C2 Validation | C3 Traffic | C4 Rollback | C5 Preserved | Pass/Fail |
|----------|----------|---------------|------------|-------------|--------------|-----------|

A PR bundle is considered PASSING only if all five elements are present 
for every PR proof validation target. Any missing element is a product gap, 
not an architecture gap.

DEPLOYMENT NOTE FOR ADVERSARIAL RESOURCES

All A-series, B-series, and C-series resources must be tagged with both 
their scenario tag (BlastRadiusTest=... or ContextTest=...) AND the 
standard group tags (TestGroup=detection or TestGroup=remediation).

Include them in the coverage matrix with an additional column:
| Control ID | Architecture | Group A Resource | Group C Resource | Group B Resource | Adversarial Scenario |

Any control that does not have at least one adversarial scenario resource 
covering it must be flagged explicitly in the coverage matrix as 
"basic coverage only — no adversarial validation."

FINAL COVERAGE MATRIX

The final deliverable is a coverage matrix with these columns:
- Control ID from Phase 1 control inventory
- Architecture it is tested in
- Group A detection resource that triggers the finding
- Group C remediation resource used to verify the fix
- Group B resource that confirms no false positive
- Adversarial Scenario (A1/A2/A3/B1/B2/B3/C or "basic coverage only")

Every Phase 1 control ID must appear. Any gap must be flagged explicitly 
rather than left blank.

--- END EXISTING TEST PLAN ---

Evaluate the existing test plan above against the gaps identified in 
Layers 1-3, flag any overlaps or redundancies, and recommend any 
modifications needed based on what you found in the codebase.

LAYER 5 — REGRESSION AND RELEASE GATE
- What checks must pass before every production deployment?
- What is the minimum viable test suite that can run in CI in under 10 minutes?
- What requires a longer nightly or pre-release run?

---

PHASE 4 — ORGANIZED TASK BACKLOG

Based on everything found in Phases 1, 2, and 3, produce a fully organized 
task backlog covering every remaining piece of work needed to reach production 
readiness. Structure it as follows:

For every task include:
- Task ID (sequential, e.g. PROD-001)
- Title (one line, action-oriented)
- Category (Backend / Frontend / Infrastructure / Testing / Security / Observability / Ops)
- Priority (Blocking / High / Medium / Low)
- Effort estimate (S = half day, M = 1-2 days, L = 3-5 days, XL = 1+ week)
- Specific file or component this task applies to
- What done looks like — one sentence definition of completion
- Dependencies — which other task IDs must be complete first

Group tasks into the following tracks and present each track separately:

  TRACK 1 — BLOCKING: ship nothing until these are done
  TRACK 2 — BACKEND COMPLETENESS: every frontend feature fully backed by working API
  TRACK 3 — END-TO-END OPERATOR EXPERIENCE: every user-facing workflow works 
             without broken states, dead ends, or missing feedback
  TRACK 4 — SECURITY HARDENING: all security gaps closed before production traffic
  TRACK 5 — OBSERVABILITY AND ALERTING: blind spots eliminated before launch
  TRACK 6 — TESTING INFRASTRUCTURE: test coverage that gives confidence to ship
  TRACK 7 — INFRASTRUCTURE AND DEPLOYMENT: repeatable, safe, zero-downtime deploys
  TRACK 8 — POST-LAUNCH: important but can follow first production release

After the full backlog, deliver a summary table:
| Track | Task Count | Blocking Count | Estimated Total Effort |
|-------|-----------|----------------|----------------------|

And a recommended execution sequence — which tracks to run in parallel, 
which must be sequential, and what the critical path to production readiness is.

---

CONSTRAINTS

- Do not change any code
- Do not make assumptions — if something is ambiguous, read more files before deciding
- Do not repeat findings from the UX audit already documented in 
  /Users/marcomaher/AWS Security Autopilot/docs/ux-audit/ux-audit-master.md 
  — treat that audit as already known and build on top of it, not over it
- Flag explicitly if any finding in this review contradicts or supersedes 
  a recommendation in the existing UX audit
- Every finding, task, and recommendation must reference a specific file, 
  component, endpoint, or infrastructure resource — nothing without a location

Stop after Phase 1 summary and wait for confirmation before proceeding to Phase 2.
