# PR Bundle Safety & Evaluation Instructions

> **Operating Manual**: Follow these guidelines to ensure engineers confidently merge automated PR bundles without fear of breaking production. All remediation logic MUST adhere to the [Thinking Strategy](thinking-strategy.md) principles of Idempotency, Blast Radius Validation, and Safe Execution.

---

## 1. PRE-FLIGHT (Blast Radius Pre-Validation)

Before generating any Pull Request, the backend MUST act as a gatekeeper and run automated pre-flight checks. No code is generated if these checks fail.

**Instructions:**
*   **API Polling Before Generation:** The worker MUST query the live AWS API to understand current usage before proposing a fix.
    *   *Example Check:* For S3 public access blocks, run `GetBucketWebsite`. If website hosting is enabled, abort the PR generation. Flag as `"High Risk of Outage"` and log to `BLOCKERS.md` or the equivalent state tracking file for that run. Propose CloudFront migration instead.
*   **Dependency Graphing:** For resources like Security Groups or IAM roles, query AWS for attached ENIs, instances, or cross-account trusts. 
    *   *Rule:* If deleting a rule or scoping a policy severs an active, recorded connection, the PR generation MUST be halted.

## 2. EXECUTION (Contextual Awareness & Idempotency)

A dangerous PR is one that overwrites existing infrastructure because it lacks context or assumes a clean slate.

**Instructions:**
*   **Append, Don't Replace (State Preservation):** If a customer has an existing complex bucket policy, security group, or IAM role, generated Terraform MUST append to or precisely modify the isolated misconfiguration. It must never replace the entire resource block.
*   **Idempotent Execution Design:** Remediation generation must be safe to re-run. If a PR bundle already exists for a finding or the infrastructure was already fixed manually, the system must detect this and skip generation rather than duplicating or erroring out.
*   **Automated Terraform Plan Validation:** The engine MUST execute a dry-run `terraform plan` against the customer's existing environment using the generated IaC.
*   **Destruction Prevention:** The system must parse the plan output. **No unexpected destruction of existing resources** is permitted (i.e., no `- destroyed` lines outside the specific fix scope). If destruction is detected, fail the task and log the diagnostic context.

## 3. VERIFICATION (The "Dry-Run" Proof)

To build trust, the PR description opened by the bot must provide explicit proof of validation and an undeniable escape hatch.

**Instructions:**
*   **Explicit Scope Copy:** Every automated PR description must include a clear, standardized safety statement. 
    *   *Required Format:* `"We validated this change against your current AWS state. It does not conflict with active traffic. If applied, this will modify exactly 1 resource and destroy 0 resources."`
*   **Actionable Rollbacks (Recovery Plan):** A destructive or modifying operation must have a documented recovery path. The PR description MUST include an exact, copy-pasteable rollback command.
    *   *Required Format:* `"Rollback Command: terraform apply -target=aws_s3_bucket.xyz -var-file=previous.tfvars"`

---
**Verification Checklist before marking Remediation feature complete:**
- [ ] Backend runs `GetBucketWebsite` or similar API checks before generation.
- [ ] Infrastructure code correctly appends to state and doesn't replace.
- [ ] Dry-run `terraform plan` validates zero unexpected resource destruction.
- [ ] Actionable rollback commands are present in all PR descriptions.
