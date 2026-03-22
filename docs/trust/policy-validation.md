# Policy Validation

Fresh IAM Access Analyzer validation was run on March 20, 2026 against the current repo-rendered role policies.

## Validation Result

| Policy | Validation mode | Result |
|---|---|---|
| ReadRole trust policy | `RESOURCE_POLICY` + `AWS::IAM::AssumeRolePolicyDocument` | `0` findings |
| ReadRole identity policy | `IDENTITY_POLICY` | `0` findings |
| WriteRole trust policy (deprecated appendix) | `RESOURCE_POLICY` + `AWS::IAM::AssumeRolePolicyDocument` | `0` findings |
| WriteRole identity policy (deprecated appendix) | `IDENTITY_POLICY` | `0` findings |

Evidence:

- [ReadRole trust validation](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/validation/read-role-trust-policy-access-analyzer.json)
- [ReadRole identity validation](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/validation/read-role-identity-policy-access-analyzer.json)
- [WriteRole trust validation appendix](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/validation/write-role-trust-policy-access-analyzer.json)
- [WriteRole identity validation appendix](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/trust-package/20260320T023532Z-buyer-trust-package/validation/write-role-identity-policy-access-analyzer.json)

## What Changed To Reach Zero Findings

- The role trust policy now keeps `sts:AssumeRole` under the `sts:ExternalId` condition and moves `sts:SetSourceIdentity` / `sts:TagSession` into a separate statement scoped only by `aws:PrincipalArn`.
- The ReadRole identity policy no longer includes the invalid action `iam:GetAccountSummaryReport`.
- The validator now treats role trust documents as `AWS::IAM::AssumeRolePolicyDocument`, which is the correct IAM Access Analyzer resource type for role trust policies.
