RAW PR-BUNDLE EXTRACTION
| Control ID or Action ID | IaC Format | Resource Type | Template Function | Source File | Source Line |
|------------------------|-----------|--------------|------------------|-------------|-------------|
| s3_block_public_access | Terraform | aws_s3_account_public_access_block | _terraform_s3_content | backend/services/pr_bundle.py | 603 |
| s3_block_public_access | CloudFormation | AWS::CloudFormation::WaitConditionHandle | _cloudformation_s3_content | backend/services/pr_bundle.py | 660 |
| enable_security_hub | Terraform | aws_securityhub_account | _terraform_security_hub_content | backend/services/pr_bundle.py | 734 |
| enable_security_hub | CloudFormation | AWS::SecurityHub::Hub | _cloudformation_security_hub_content | backend/services/pr_bundle.py | 755 |
| enable_guardduty | Terraform | aws_guardduty_detector | _terraform_guardduty_content | backend/services/pr_bundle.py | 828 |
| enable_guardduty | CloudFormation | AWS::GuardDuty::Detector | _cloudformation_guardduty_content | backend/services/pr_bundle.py | 851 |
| s3_bucket_block_public_access | Terraform | aws_s3_bucket_public_access_block | _terraform_s3_bucket_block_content | backend/services/pr_bundle.py | 957 |
| s3_bucket_block_public_access | CloudFormation | AWS::S3::Bucket | _cloudformation_s3_bucket_block_content | backend/services/pr_bundle.py | 1147 |
| s3_bucket_block_public_access (strategy: s3_migrate_cloudfront_oac_private) | Terraform | aws_cloudfront_origin_access_control | _terraform_s3_cloudfront_oac_private_content | backend/services/pr_bundle.py | 1021 |
| s3_bucket_block_public_access (strategy: s3_migrate_cloudfront_oac_private) | Terraform | aws_cloudfront_distribution | _terraform_s3_cloudfront_oac_private_content | backend/services/pr_bundle.py | 1029 |
| s3_bucket_block_public_access (strategy: s3_migrate_cloudfront_oac_private) | Terraform | aws_s3_bucket_policy | _terraform_s3_cloudfront_oac_private_content | backend/services/pr_bundle.py | 1097 |
| s3_bucket_block_public_access (strategy: s3_migrate_cloudfront_oac_private) | Terraform | aws_s3_bucket_public_access_block | _terraform_s3_cloudfront_oac_private_content | backend/services/pr_bundle.py | 1102 |
| s3_bucket_encryption | Terraform | aws_s3_bucket_server_side_encryption_configuration | _terraform_s3_bucket_encryption_content | backend/services/pr_bundle.py | 1211 |
| s3_bucket_encryption | CloudFormation | AWS::S3::Bucket | _cloudformation_s3_bucket_encryption_content | backend/services/pr_bundle.py | 1241 |
| s3_bucket_access_logging | Terraform | aws_s3_bucket_logging | _terraform_s3_bucket_access_logging_content | backend/services/pr_bundle.py | 1322 |
| s3_bucket_access_logging | CloudFormation | AWS::S3::Bucket | _cloudformation_s3_bucket_access_logging_content | backend/services/pr_bundle.py | 1355 |
| s3_bucket_lifecycle_configuration | Terraform | aws_s3_bucket_lifecycle_configuration | _terraform_s3_bucket_lifecycle_configuration_content | backend/services/pr_bundle.py | 1419 |
| s3_bucket_lifecycle_configuration | CloudFormation | AWS::S3::Bucket | _cloudformation_s3_bucket_lifecycle_configuration_content | backend/services/pr_bundle.py | 1457 |
| s3_bucket_encryption_kms | Terraform | aws_s3_bucket_server_side_encryption_configuration | _terraform_s3_bucket_encryption_kms_content | backend/services/pr_bundle.py | 1528 |
| s3_bucket_encryption_kms | CloudFormation | AWS::S3::Bucket | _cloudformation_s3_bucket_encryption_kms_content | backend/services/pr_bundle.py | 1563 |
| sg_restrict_public_ports | Terraform | null_resource | _terraform_sg_restrict_content | backend/services/pr_bundle.py | 1679 |
| sg_restrict_public_ports | Terraform | aws_vpc_security_group_ingress_rule | _terraform_sg_restrict_content | backend/services/pr_bundle.py | 1708 |
| sg_restrict_public_ports | CloudFormation | AWS::EC2::SecurityGroupIngress | _cloudformation_sg_restrict_content | backend/services/pr_bundle.py | 1787 |
| cloudtrail_enabled | Terraform | aws_cloudtrail | _terraform_cloudtrail_content | backend/services/pr_bundle.py | 1909 |
| cloudtrail_enabled | CloudFormation | AWS::CloudTrail::Trail | _cloudformation_cloudtrail_content | backend/services/pr_bundle.py | 1934 |
| aws_config_enabled | Terraform | null_resource | _terraform_aws_config_enabled_content | backend/services/pr_bundle.py | 2310 |
| aws_config_enabled (strategy: config_enable_account_local_delivery) | CloudFormation | AWS::S3::Bucket | _cloudformation_aws_config_enabled_content | backend/services/pr_bundle.py | 2388 |
| aws_config_enabled | CloudFormation | AWS::Config::ConfigurationRecorder | _cloudformation_aws_config_enabled_content | backend/services/pr_bundle.py | 2408 |
| aws_config_enabled | CloudFormation | AWS::Config::DeliveryChannel | _cloudformation_aws_config_enabled_content | backend/services/pr_bundle.py | 2415 |
| ssm_block_public_sharing | Terraform | aws_ssm_service_setting | _terraform_ssm_block_public_sharing_content | backend/services/pr_bundle.py | 2429 |
| ssm_block_public_sharing | CloudFormation | AWS::IAM::Role | _cloudformation_ssm_block_public_sharing_content | backend/services/pr_bundle.py | 2445 |
| ssm_block_public_sharing | CloudFormation | AWS::Lambda::Function | _cloudformation_ssm_block_public_sharing_content | backend/services/pr_bundle.py | 2471 |
| ssm_block_public_sharing | CloudFormation | Custom::SSMServiceSetting | _cloudformation_ssm_block_public_sharing_content | backend/services/pr_bundle.py | 2493 |
| ebs_snapshot_block_public_access | Terraform | aws_ebs_snapshot_block_public_access | _terraform_ebs_snapshot_block_public_access_content | backend/services/pr_bundle.py | 2501 |
| ebs_snapshot_block_public_access | CloudFormation | AWS::EC2::SnapshotBlockPublicAccess | _cloudformation_ebs_snapshot_block_public_access_content | backend/services/pr_bundle.py | 2512 |
| ebs_default_encryption (strategy: ebs_enable_default_encryption_customer_kms) | Terraform | aws_ebs_default_kms_key | _terraform_ebs_default_encryption_content | backend/services/pr_bundle.py | 2527 |
| ebs_default_encryption | Terraform | aws_ebs_encryption_by_default | _terraform_ebs_default_encryption_content | backend/services/pr_bundle.py | 2532 |
| ebs_default_encryption | CloudFormation | AWS::IAM::Role | _cloudformation_ebs_default_encryption_content | backend/services/pr_bundle.py | 2553 |
| ebs_default_encryption | CloudFormation | AWS::Lambda::Function | _cloudformation_ebs_default_encryption_content | backend/services/pr_bundle.py | 2581 |
| ebs_default_encryption | CloudFormation | Custom::EbsDefaultEncryption | _cloudformation_ebs_default_encryption_content | backend/services/pr_bundle.py | 2601 |
| s3_bucket_require_ssl | Terraform | aws_s3_bucket_policy | _terraform_s3_bucket_require_ssl_content | backend/services/pr_bundle.py | 2650 |
| s3_bucket_require_ssl | CloudFormation | AWS::S3::BucketPolicy | _cloudformation_s3_bucket_require_ssl_content | backend/services/pr_bundle.py | 2677 |
| iam_root_access_key_absent | Terraform | null_resource | _terraform_iam_root_access_key_absent_content | backend/services/pr_bundle.py | 2720 |

FILES READ (with line counts)
- backend/services/pr_bundle.py — 2811 lines
- infrastructure/cloudformation/control-plane-forwarder-template.yaml — 221 lines — No pr-bundle IaC generation logic.
- infrastructure/cloudformation/read-role-template.yaml — 328 lines — No pr-bundle IaC generation logic.
- infrastructure/cloudformation/reconcile-scheduler-template.yaml — 229 lines — No pr-bundle IaC generation logic.
- infrastructure/cloudformation/write-role-template.yaml — 295 lines — No pr-bundle IaC generation logic.
- frontend/src/components/RemediationRunProgress.tsx — 755 lines — No pr-bundle IaC generation logic.
- infrastructure/cloudformation/edge-protection.yaml — 233 lines — No pr-bundle IaC generation logic.
- scripts/config/no_ui_pr_bundle_agent.example.json — 20 lines — No pr-bundle IaC generation logic.
- scripts/deploy_finding_bundle.sh — 44 lines — No pr-bundle IaC generation logic.
- scripts/destroy_finding_bundle.sh — 44 lines — No pr-bundle IaC generation logic.
- scripts/upload_control_plane_forwarder_template.py — 57 lines — No pr-bundle IaC generation logic.

Output file written: docs/prod-readiness/06-task6-raw-pr-bundle.md
Output file line count: 62
