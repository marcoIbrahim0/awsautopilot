# Hardening Strategy for PR Bundle Actions

Currently, the `no-ui-pr-bundle-agent` protects Terraform applies holistically using a strict deletion allowlist. To further harden each of the 16 supported actions individually, we need to focus on **action-specific validations**, **drift detection**, and **state pre-checks**.

Here is a proposed breakdown for how to harden each action individually:

## 1. s3_block_public_access (Account-level block)
- **Pre-flight:** Query `s3control:GetPublicAccessBlock` to ensure it's not already rigidly managed by an AWS Organization SCP. 
- **Hardening:** Reject the PR bundle if the account is part of an Org that enforces this centrally, avoiding execution loops.

## 2. s3_bucket_block_public_access
- **Pre-flight:** Ensure cross-region replication streams or CloudFront distributions aren't relying on public readable ACLs *before* generating the bundle (currently we warn, but we should actively *block* generation if we detect legacy active traffic).
- **Hardening:** Terraform applies often fail if the bucket is locked by an SCP. Pre-flight should check for `AccessDenied` on `PutPublicAccessBlock`.

## 3. s3_bucket_require_ssl
- **Pre-flight:** Parse the existing bucket policy (if present) to confirm we aren't creating a duplicate `DenyInsecureTransport` statement which makes the policy bloated.
- **Hardening:** Validate that the merged policy size does not exceed the 20KB AWS bucket policy limit before applying.

## 4. s3_bucket_access_logging
- **Pre-flight:** Validate the *target* logging bucket actually exists, is in the same region, and has the correct `s3:PutObject` permissions for the delivery service *before* writing the Terraform output.
- **Hardening:** Dynamically query suitable logging buckets in the account so the user doesn't have to guess one.

## 5. s3_bucket_lifecycle_configuration
- **Pre-flight:** Pull existing lifecycle rules to ensure our generated `security_autopilot_abort_incomplete_multipart` rule doesn't conflict with or shadow an existing abort rule.
- **Hardening:** Merge existing rules natively rather than replacing the lifecycle configuration entirely (similar to what was done for S3.5 bucket policies).

## 6. s3_bucket_encryption & 7. s3_bucket_encryption_kms
- **Pre-flight:** Check if the bucket is already encrypted with a customer-managed KMS key.
- **Hardening:** Downgrading encryption (e.g. KMS to AES256) should be strictly blocked by the agent. Pre-flight should verify the KMS key policy allows the bucket to use it before generating the bundle.

## 8. sg_restrict_public_ports
- **Pre-flight:** Beyond just looking for active ENIs, we should look at AWS VPC Flow Logs if available to see if the port *actually receives traffic*.
- **Hardening:** If fixing port 22/3389, we should inject SSM Session Manager policies instead of leaving the user without access, offering a "secure alternative" bundle rather than just a destructive one.

## 9. enable_security_hub
- **Pre-flight:** Security Hub requires AWS Config to be enabled. Pre-flight MUST verify Config is enabled in the target region first.
- **Hardening:** Provide a multi-step PR bundle (Enable Config -> Enable SecurityHub) if Config is missing.

## 10. enable_guardduty
- **Hardening:** GuardDuty is a regional service. Hardening this action means supporting an organizational deployment model if the account is an Org root, rather than just single-account/single-region.

## 11. cloudtrail_enabled
- **Pre-flight:** Check if an Organization-level trail already exists covering the account. If so, generating a local trail is redundant and costs money.
- **Hardening:** Ensure the attached S3 bucket for the trail has an exact, secure bucket policy generated dynamically alongside the trail.

## 12. aws_config_enabled
- **Pre-flight:** AWS Config allows only one configuration recorder per region. 
- **Hardening:** Pre-flight MUST check for existing recorders (`aws configservice describe-configuration-recorders`) and merge/update rather than trying to blindly create a new one (which will fail).

## 13. ssm_block_public_sharing
- **Hardening:** This is an account-level setting. The action should strictly confirm the setter has permissions across all active regions. The agent could auto-loop across active regions during the run.

## 14. ebs_snapshot_block_public_access
- **Pre-flight:** Check if there are *currently* public snapshots in the account that the user intended to share.
- **Hardening:** Expose an exception list in the Terraform module if they have legitimately public AMIs/Snapshots.

## 15. ebs_default_encryption
- **Hardening:** Verify the default KMS key is valid and not pending deletion. Ensure the IAM role running the agent has grants to use that key, otherwise future EC2 instance launches will fail.

## 16. iam_root_access_key_absent
- **Hardening:** Generating a PR bundle for this is tough because Terraform cannot delete root access keys. 
- **Resolution:** This action should be converted to a pure "Instructions-only" bundle or generate a specific incident response runbook rather than attempting IaC.
