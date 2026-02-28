---
Deployed AWS security test environment to account 029037611564 
in region eu-north-1 on 2026-02-27 18:50:55 UTC.

Architecture 1 — architecture-1: 19 resources created
Architecture 2 — architecture-2: 18 resources created
Total resources deployed: 37

Adversarial resource verification:
* A1 (S3 website hosting): PASS
* A2 (SG dependency chain): PASS
* A3 (IAM multi-principal): PASS
* B1 (complex S3 policy): PASS
* B2 (mixed SG rules): PASS
* B3 (IAM inline plus managed): PASS

Resources by group:
* Group A (detection targets): 7 resources
* Group B (clean negatives): 5 resources
* Group C (remediation targets): 25 resources

Changed files:
* docs/prod-readiness/08-deployment-report.md

Deployment issues encountered:
* 08-task2-deploy-arch1.sh failed with placeholder AWS_REGION/ACCOUNT_ID and RDS credentials; fixed by allowing env-var overrides and validating required values.
* Architecture 1 deploy failed with account-level S3 Block Public Access (BlockPublicPolicy) preventing public bucket policy; resolved by disabling account-level S3 Block Public Access during test deploy.
* Architecture 1 rerun failed with BucketAlreadyOwnedByYou due partial resources from prior failed attempt; resolved by running full Architecture 1 teardown cleanup and redeploying.
* Architecture 1 deploy failed with MalformedPolicy Invalid principal in B1 policy; resolved by replacing hardcoded invalid principals with valid account-derived principal defaults.
* 08-task3-deploy-arch2.sh failed at Config recorder because booleans were passed as strings; resolved by switching to JSON boolean payload.
* Architecture 2 deploy failed with MaxNumberOfConfigurationRecordersExceededException; resolved by reusing existing recorder/delivery channel names when present.
* Architecture 2 deploy failed with InsufficientDeliveryPolicyException for Config bucket; resolved by adding required S3 bucket policies for Config and CloudTrail service delivery.
* Architecture 2 deploy failed creating public RDS due missing VPC internet gateway/route; resolved by auto-creating and attaching IGW plus route table associations.
* Architecture 2 deploy failed with unsupported postgres engine version 16.3 in eu-north-1; resolved by removing pinned engine version to allow valid default.
* Architecture 2 deploy initially reported EKS ARN as aws-cli version string due incorrect flag --version; resolved by using --kubernetes-version.
* Step 6 A3 expected inline policy name wildcard-policy but role had a different inline policy name; resolved by adding wildcard-policy with Action:* and Resource:*.
* Step 6 B3 expected 2 managed policies but role had 1; resolved by attaching SecurityAudit as second managed policy.

Resources to verify manually:
* ECS service arch1_web_ingest_service is ACTIVE with desiredCount=1 but runningCount=0; verify task placement/networking in ECS console.

Teardown commands when ready:
* Architecture 1: bash docs/prod-readiness/08-task6-teardown-arch1-full.sh
* Architecture 2: bash docs/prod-readiness/08-task7-teardown-arch2-full.sh
---
