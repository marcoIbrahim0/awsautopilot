SECTION 1 — CONTROL INVENTORY SUMMARY
| Control ID | Control Name | AWS Service | Action Type (direct-fix / pr-bundle) |
|------------|-------------|-------------|--------------------------------------|
| S3.1 | S3 account public access hardening | s3control | direct-fix + pr-bundle |
| SecurityHub.1 | Enable Security Hub | securityhub | direct-fix + pr-bundle |
| GuardDuty.1 | Enable GuardDuty | guardduty | direct-fix + pr-bundle |
| S3.2 | Enforce S3 bucket public access hardening | s3 | pr-bundle |
| S3.4 | Enforce S3 bucket encryption | s3 | pr-bundle |
| EC2.53 | Restrict security-group public ports | ec2 | pr-bundle |
| CloudTrail.1 | Enable CloudTrail | cloudtrail | pr-bundle |
| Config.1 | Enable AWS Config recording | config | pr-bundle |
| SSM.7 | Block public SSM document sharing | ssm | pr-bundle |
| EC2.182 | Restrict EBS snapshot public sharing | ec2 | pr-bundle |
| EC2.7 | Enable EBS default encryption | ec2 | direct-fix + pr-bundle |
| S3.5 | Enforce SSL-only S3 access | s3 | pr-bundle |
| IAM.4 | Remove IAM root access keys | iam | pr-bundle |
| S3.9 | Enable S3 bucket access logging | s3 | pr-bundle |
| S3.11 | Configure S3 bucket lifecycle | s3 | pr-bundle |
| S3.15 | Enforce S3 bucket SSE-KMS encryption | s3 | pr-bundle |
| S3.3 | Alias of S3.2 | s3 | pr-bundle |
| S3.8 | Alias of S3.2 | s3 | pr-bundle |
| S3.17 | Alias of S3.2 | s3 | pr-bundle |
| EC2.13 | Alias of EC2.53 | ec2 | pr-bundle |
| EC2.18 | Alias of EC2.53 | ec2 | pr-bundle |
| EC2.19 | Alias of EC2.53 | ec2 | pr-bundle |
| RDS.PUBLIC_ACCESS | RDS instance public network exposure (inventory-only signal) | rds | pr-bundle (pr_only; unsupported) |
| RDS.ENCRYPTION | RDS storage encryption at rest (inventory-only signal) | rds | pr-bundle (pr_only; unsupported) |
| EKS.PUBLIC_ENDPOINT | EKS API public endpoint exposure (inventory-only signal) | eks | pr-bundle (pr_only; unsupported) |

SECTION 2 — ACTION TYPE SUMMARY
| Action ID | Action Name | Type | AWS API or IaC resource |
|-----------|-------------|------|------------------------|
| pr_only | PR-only action (unmapped/default) | pr-bundle | UNKNOWN |
| direct_fix | direct_fix (preview mode) | direct-fix | UNKNOWN |
| pr_bundle | PR bundle mode | pr-bundle | UNKNOWN |
| s3_block_public_access | S3 account public access hardening | direct-fix + pr-bundle | API: s3control.put_public_access_block; IaC: aws_s3_account_public_access_block, AWS::CloudFormation::WaitConditionHandle |
| enable_security_hub | Enable Security Hub | direct-fix + pr-bundle | API: securityhub.enable_security_hub; IaC: aws_securityhub_account, AWS::SecurityHub::Hub |
| enable_guardduty | Enable GuardDuty | direct-fix + pr-bundle | API: guardduty.create_detector, guardduty.update_detector; IaC: aws_guardduty_detector, AWS::GuardDuty::Detector |
| s3_bucket_block_public_access | Enforce S3 bucket public access hardening | pr-bundle | IaC: aws_s3_bucket_public_access_block, AWS::S3::Bucket |
| s3_bucket_encryption | Enforce S3 bucket encryption | pr-bundle | IaC: aws_s3_bucket_server_side_encryption_configuration, AWS::S3::Bucket |
| s3_bucket_access_logging | Enable S3 bucket access logging | pr-bundle | IaC: aws_s3_bucket_logging, AWS::S3::Bucket |
| s3_bucket_lifecycle_configuration | Configure S3 bucket lifecycle | pr-bundle | IaC: aws_s3_bucket_lifecycle_configuration, AWS::S3::Bucket |
| s3_bucket_encryption_kms | Enforce S3 bucket SSE-KMS encryption | pr-bundle | IaC: aws_s3_bucket_server_side_encryption_configuration, AWS::S3::Bucket |
| sg_restrict_public_ports | Restrict security-group public ports | pr-bundle | IaC: aws_vpc_security_group_ingress_rule, AWS::EC2::SecurityGroupIngress |
| cloudtrail_enabled | Enable CloudTrail | pr-bundle | IaC: aws_cloudtrail, AWS::CloudTrail::Trail |
| aws_config_enabled | Enable AWS Config recording | pr-bundle | IaC: AWS::Config::ConfigurationRecorder, AWS::Config::DeliveryChannel |
| ssm_block_public_sharing | Block public SSM document sharing | pr-bundle | IaC: aws_ssm_service_setting, Custom::SSMServiceSetting |
| ebs_snapshot_block_public_access | Restrict EBS snapshot public sharing | pr-bundle | IaC: aws_ebs_snapshot_block_public_access, AWS::EC2::SnapshotBlockPublicAccess |
| ebs_default_encryption | Enable EBS default encryption | direct-fix + pr-bundle | API: ec2.enable_ebs_encryption_by_default, ec2.modify_ebs_default_kms_key_id; IaC: aws_ebs_encryption_by_default, aws_ebs_default_kms_key, Custom::EbsDefaultEncryption |
| s3_bucket_require_ssl | Enforce SSL-only S3 access | pr-bundle | IaC: aws_s3_bucket_policy, AWS::S3::BucketPolicy |
| iam_root_access_key_absent | Remove IAM root access keys | pr-bundle | IaC: Terraform null_resource only in extracted PR-bundle data |

SECTION 3 — COVERAGE REQUIREMENTS
- Total controls to cover: 25 (runtime controls; excludes ARC-008 `INFRA_METADATA_ONLY` metadata row)
- Controls requiring direct-fix coverage: 4
- Controls requiring pr-bundle coverage: 25
- AWS services involved: s3control, securityhub, guardduty, s3, ec2, cloudtrail, config, ssm, iam, rds, eks
- Minimum distinct AWS service categories needed: 11

SECTION 4 — VALIDATION FLAGS
- Action ID `pr_only`: AWS API or IaC change is UNKNOWN.
- Action ID `direct_fix`: AWS API or IaC change is UNKNOWN.
- Action ID `pr_bundle`: AWS API or IaC change is UNKNOWN.
