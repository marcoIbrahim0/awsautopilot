# 07 Task5 B-Series Adversarial Resources

This document defines the three B-series adversarial resources for later embedding into architectures. No architecture assignment is made in this task.

## B1 - S3 bucket with complex existing policy

| Field | Value |
|-------|-------|
| Resource type | Amazon S3 bucket (`aws_s3_bucket`) with bucket policy (`aws_s3_bucket_policy`) and bucket-level public access block (`aws_s3_bucket_public_access_block`) |
| Existing legitimate configuration | 1) Bucket policy statement allows cross-account read access to AWS account `123456789012`.<br>2) Bucket policy statement allows `s3:PutObject` for role `arn:aws:iam::111122223333:role/DataPipelineRole`.<br>3) Bucket policy statement includes a condition block using `aws:SourceVpc` to scope access to the expected VPC source path. |
| Misconfiguration to remediate | Public access block is disabled on the bucket. |
| What a destructive wrong terraform plan would show | Plan rewrites or replaces `aws_s3_bucket_policy` and drops one or more legitimate statements (cross-account read, `DataPipelineRole` write, or the `aws:SourceVpc`-conditioned statement) while trying to fix exposure. It may show policy statement deletions or full policy replacement instead of a targeted public-access-block update. |
| What a correct terraform plan would show | Plan changes only `aws_s3_bucket_public_access_block` for this bucket (set `block_public_acls=true`, `ignore_public_acls=true`, `block_public_policy=true`, `restrict_public_buckets=true`). Existing bucket policy statements remain unchanged. |
| Required tag | `ContextTest=existing-complex-policy` |

## B2 - Security group with mixed legitimate and permissive rules

| Field | Value |
|-------|-------|
| Resource type | Amazon EC2 security group (`aws_security_group` with ingress-rule resources such as `aws_vpc_security_group_ingress_rule`) |
| Existing legitimate rules | 1) Inbound TCP `443` from CIDR `10.0.0.0/16`.<br>2) Inbound TCP `5432` from source security group `sg-0a1b2c3d4e5f`.<br>3) Inbound TCP `8080` from specific IP `203.0.113.10/32`. |
| Misconfiguration to remediate | Inbound TCP `22` from `0.0.0.0/0`. |
| What a destructive wrong terraform plan would show | Plan removes or replaces the whole ingress set and deletes legitimate rules (`443` from `10.0.0.0/16`, `5432` from `sg-0a1b2c3d4e5f`, and/or `8080` from `203.0.113.10/32`) instead of only removing the public SSH rule. |
| What a correct terraform plan would show | Plan removes only the permissive SSH ingress rule (`22` from `0.0.0.0/0`). The three legitimate inbound rules remain unchanged. |
| Required tag | `ContextTest=mixed-sg-rules` |

## B3 - IAM role with managed plus inline policy

| Field | Value |
|-------|-------|
| Resource type | AWS IAM role (`aws_iam_role`) with managed policy attachments (`aws_iam_role_policy_attachment`) and inline policy (`aws_iam_role_policy`) |
| Existing legitimate configuration | Role has two AWS managed policies attached and both must be preserved: `AmazonS3ReadOnlyAccess` and `AmazonEC2ReadOnlyAccess`. |
| Misconfiguration to remediate | Inline policy grants wildcard permissions (`Action: *`, `Resource: *`). |
| What a destructive wrong terraform plan would show | Plan detaches or destroys legitimate managed policy attachments (`AmazonS3ReadOnlyAccess`, `AmazonEC2ReadOnlyAccess`) or replaces/deletes the role while removing the inline wildcard policy. |
| What a correct terraform plan would show | Plan updates or removes only the inline wildcard policy. Managed policy attachments (`AmazonS3ReadOnlyAccess`, `AmazonEC2ReadOnlyAccess`) remain attached with no changes. |
| Required tag | `ContextTest=inline-plus-managed` |
