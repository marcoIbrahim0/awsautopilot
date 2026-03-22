# Least Privilege

The current product trust boundary is `ReadRole` only. No customer-facing write-capable role is part of the active remediation contract.

## Boundary Summary

| Surface | Current rule | Evidence |
|---|---|---|
| Customer role in scope | `SecurityAutopilotReadRole` only | [Connect your AWS account](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/connecting-aws.md), [WriteRole status](/Users/marcomaher/AWS%20Security%20Autopilot/docs/connect-write-role.md) |
| Trust principal | SaaS account root constrained by exact `aws:PrincipalArn` execution roles | [Rendered ReadRole trust policy](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/rendered/read-role-trust-policy.json) |
| External binding | `sts:ExternalId` required on `sts:AssumeRole` | [Rendered ReadRole trust policy](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/rendered/read-role-trust-policy.json) |
| Session audit context | `sts:SetSourceIdentity` and `sts:TagSession` allowed only for the same execution role ARN set, in a separate statement from `ExternalId` | [Rendered ReadRole trust policy](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/rendered/read-role-trust-policy.json) |
| Runtime teardown | `ALLOW_RUNTIME_IAM_CLEANUP=false` by default; customer CloudFormation stack deletion is the preferred teardown path | [Connecting your AWS account](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/connecting-aws.md), [Secrets & configuration management](/Users/marcomaher/AWS%20Security%20Autopilot/docs/deployment/secrets-config.md) |
| Deprecated appendix only | `WriteRole` exists for backward-compatible reference but is not part of the active onboarding or remediation contract | [WriteRole status](/Users/marcomaher/AWS%20Security%20Autopilot/docs/connect-write-role.md), [Rendered WriteRole trust policy appendix](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/rendered/write-role-trust-policy.json) |

## ReadRole Permission Inventory

| Service area | Actions |
|---|---|
| Security Hub | `securityhub:GetFindings`, `securityhub:DescribeHub` |
| AWS Config | `config:DescribeConfigurationRecorders`, `config:DescribeConfigurationRecorderStatus`, `config:DescribeDeliveryChannels`, `config:DescribeConfigRules`, `config:DescribeComplianceByConfigRule`, `config:GetComplianceDetailsByConfigRule` |
| EC2 | `ec2:DescribeSecurityGroups`, `ec2:DescribeSecurityGroupRules`, `ec2:GetEbsEncryptionByDefault`, `ec2:GetSnapshotBlockPublicAccessState` |
| S3 | `s3:GetBucketPolicyStatus`, `s3:GetBucketPolicy`, `s3:GetBucketAcl`, `s3:GetBucketPublicAccessBlock`, `s3:GetBucketLocation`, `s3:GetEncryptionConfiguration`, `s3:GetBucketLogging`, `s3:GetLifecycleConfiguration`, `s3:ListAllMyBuckets` |
| CloudTrail | `cloudtrail:DescribeTrails`, `cloudtrail:GetTrailStatus` |
| IAM / STS | `iam:GetAccountSummary`, `sts:GetCallerIdentity` |
| Additional inventory sources | `rds:DescribeDBInstances`, `eks:ListClusters`, `eks:DescribeCluster`, `ssm:GetServiceSetting`, `access-analyzer:ListAnalyzers`, `access-analyzer:ListFindings`, `access-analyzer:GetFinding`, `inspector2:ListFindings`, `inspector2:BatchGetAccountStatus` |

Full rendered policy JSON is in [read-role-identity-policy.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/rendered/read-role-identity-policy.json).

## Live Customer Evidence

- [Redacted live ReadRole document from the March 20 closure rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/evidence/aws/authoritative-live-read-role-redacted.json)
- [Redacted live stack summary from the March 20 closure rerun](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/evidence/aws/authoritative-live-stack-summary.json)
