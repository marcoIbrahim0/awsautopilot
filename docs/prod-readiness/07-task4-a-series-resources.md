# A-Series Adversarial Resources

## A1 — S3 bucket blast radius resource

| Field | Value |
|-------|-------|
| Resource type | Amazon S3 bucket (static website hosting) |
| Misconfiguration | Static website hosting enabled (`IndexDocument` and `ErrorDocument`), bucket policy grants `s3:GetObject` to `Principal: "*"`, bucket public access block disabled, and at least one object (`index.html`) is uploaded with no CloudFront distribution in front of the bucket. |
| Naive remediation | Enabling bucket public access block would block public object reads and cause the website endpoint to return access errors. |
| Blast radius risk | The public website would become unavailable (outage) because anonymous users could no longer fetch the website objects. |
| Correct remediation | Propose a dependency-aware remediation path that preserves required website availability instead of immediately enabling bucket public access block. |
| AWS API signal to detect risk | `GetBucketWebsite` |
| Required tag | BlastRadiusTest=website-hosting |

## A2 — Security group dependency chain resource

| Field | Value |
|-------|-------|
| Resource type | Amazon EC2 security group (`SG-A`) with transitive dependencies (EC2, RDS, and SG reference chain) |
| Misconfiguration | `SG-A` has inbound `0.0.0.0/0` on port `22`, is attached to a running EC2 instance, is also used by an RDS instance, and is referenced by `SG-B` as an inbound source. |
| Naive remediation | Deleting the `0.0.0.0/0` port `22` rule without dependency analysis can remove required inbound SSH access paths. |
| Blast radius risk | Dependent resources can be impacted across the chain: the running EC2 instance attached to `SG-A`, the RDS instance using `SG-A`, and the `SG-B` inbound rule that references `SG-A` as its source. |
| Correct remediation | Enumerate all `SG-A` dependencies before acting: attached network interfaces/resources and security groups that reference `SG-A` as a source. |
| AWS API signal to detect risk | `DescribeNetworkInterfaces` |
| Required tag | BlastRadiusTest=sg-dependency-chain |

## A3 — IAM multi-principal role resource

| Field | Value |
|-------|-------|
| Resource type | AWS IAM role shared by multiple service principals (EC2 instance profile and Lambda execution role) |
| Misconfiguration | IAM role has an inline policy with `Action:*` and `Resource:*`, is attached to a running EC2 instance profile, is used as a Lambda execution role, and trust policy allows both `ec2.amazonaws.com` and `lambda.amazonaws.com`. |
| Naive remediation | Scoping the policy without usage context can remove permissions required by one or both workloads currently using the same role. |
| Blast radius risk | Both EC2 and Lambda workloads using the role can lose required permissions. |
| Correct remediation | Enumerate all role consumers and usage context before changing scope, including EC2 instance-profile use and Lambda execution-role use of the same role. |
| AWS API signal to detect risk | `ListEntitiesForPolicy` |
| Required tag | BlastRadiusTest=iam-multi-principal |
