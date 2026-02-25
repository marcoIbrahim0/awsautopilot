SECTION 1 — ARCHITECTURE 1 COMPLETE RESOURCE INVENTORY
| Resource Name | AWS Type | Group (A/B/C) | Tier | Control IDs | Adversarial Tag | All Required Tags | Create Dependencies (must exist before this) | Delete Dependencies (must be deleted before this) |
|---|---|---|---|---|---|---|---|---|
| arch1_vpc_main | AWS::EC2::VPC | C | Tier 2 | N/A | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=workflow-processing; ResourceGroup=C | none | arch1_public_subnet_a, arch1_private_subnet_a, arch1_sg_app_b2, arch1_sg_dependency_a2, arch1_sg_reference_a2 |
| arch1_public_subnet_a | AWS::EC2::Subnet | C | Tier 1 | N/A | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=external-intake; ResourceGroup=C | arch1_vpc_main | arch1_app_server_a2, arch1_web_ingest_service |
| arch1_private_subnet_a | AWS::EC2::Subnet | C | Tier 3 | N/A | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=data-retention; ResourceGroup=C | arch1_vpc_main | arch1_claims_db_a2 |
| arch1_sg_app_b2 | AWS::EC2::SecurityGroup | B | Tier 1 | EC2.53, EC2.13, EC2.18, EC2.19 | ContextTest=mixed-sg-rules | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=external-intake; ResourceGroup=B; ContextTest=mixed-sg-rules | arch1_vpc_main | arch1_web_ingest_service |
| arch1_sg_dependency_a2 | AWS::EC2::SecurityGroup | A | Tier 2 | EC2.53, EC2.13, EC2.18, EC2.19 | BlastRadiusTest=sg-dependency-chain | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=workflow-processing; ResourceGroup=A; BlastRadiusTest=sg-dependency-chain | arch1_vpc_main | arch1_app_server_a2, arch1_claims_db_a2, arch1_sg_reference_a2 |
| arch1_sg_reference_a2 | AWS::EC2::SecurityGroup | A | Tier 2 | EC2.53, EC2.13, EC2.18, EC2.19 | BlastRadiusTest=sg-dependency-chain | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=workflow-processing; ResourceGroup=A; BlastRadiusTest=sg-dependency-chain | arch1_vpc_main, arch1_sg_dependency_a2 | none |
| arch1_app_server_a2 | AWS::EC2::Instance | A | Tier 2 | EC2.53, EC2.13, EC2.18, EC2.19 | BlastRadiusTest=sg-dependency-chain | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=workflow-processing; ResourceGroup=A; BlastRadiusTest=sg-dependency-chain | arch1_public_subnet_a, arch1_sg_dependency_a2 | none |
| arch1_claims_db_a2 | AWS::RDS::DBInstance | A | Tier 3 | EC2.53, EC2.13, EC2.18, EC2.19 | BlastRadiusTest=sg-dependency-chain | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=data-retention; ResourceGroup=A; BlastRadiusTest=sg-dependency-chain | arch1_private_subnet_a, arch1_sg_dependency_a2 | none |
| arch1_bucket_website_a1 | AWS::S3::Bucket | A | Tier 1 | S3.2, S3.3, S3.8, S3.17 | BlastRadiusTest=website-hosting | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=external-intake; ResourceGroup=A; BlastRadiusTest=website-hosting | none | arch1_bucket_policy_website_a1 |
| arch1_bucket_policy_website_a1 | AWS::S3::BucketPolicy | A | Tier 1 | S3.5 | BlastRadiusTest=website-hosting | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=external-intake; ResourceGroup=A; BlastRadiusTest=website-hosting | arch1_bucket_website_a1 | none |
| arch1_bucket_evidence_b1 | AWS::S3::Bucket | B | Tier 3 | S3.2, S3.3, S3.8, S3.17 | ContextTest=existing-complex-policy | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=data-retention; ResourceGroup=B; ContextTest=existing-complex-policy | none | arch1_bucket_policy_evidence_b1, arch1_bucket_pab_evidence_b1 |
| arch1_bucket_policy_evidence_b1 | AWS::S3::BucketPolicy | B | Tier 3 | S3.5 | ContextTest=existing-complex-policy | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=data-retention; ResourceGroup=B; ContextTest=existing-complex-policy | arch1_bucket_evidence_b1 | none |
| arch1_bucket_pab_evidence_b1 | AWS::S3::BucketPublicAccessBlock | B | Tier 3 | S3.2, S3.3, S3.8, S3.17 | ContextTest=existing-complex-policy | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=data-retention; ResourceGroup=B; ContextTest=existing-complex-policy | arch1_bucket_evidence_b1 | none |
| arch1_bucket_ingest_c | AWS::S3::Bucket | C | Tier 3 | S3.2, S3.3, S3.4, S3.8, S3.9, S3.11, S3.15, S3.17 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=data-retention; ResourceGroup=C | none | arch1_bucket_policy_ingest_c |
| arch1_bucket_policy_ingest_c | AWS::S3::BucketPolicy | C | Tier 3 | S3.5 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=data-retention; ResourceGroup=C | arch1_bucket_ingest_c | none |
| arch1_bucket_logging_target_c | AWS::S3::Bucket | C | Tier 3 | S3.9 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=data-retention; ResourceGroup=C | none | none |
| arch1_account_pab_c | s3control:PutPublicAccessBlock (account setting) | C | Tier 4 | S3.1 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=operations-access; ResourceGroup=C | none | none |
| arch1_web_ingest_service | AWS::ECS::Service | C | Tier 1 | N/A | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-1; Tier=external-intake; ResourceGroup=C | arch1_public_subnet_a, arch1_sg_app_b2 | none |

SECTION 2 — ARCHITECTURE 2 COMPLETE RESOURCE INVENTORY
| Resource Name | AWS Type | Group (A/B/C) | Tier | Control IDs | Adversarial Tag | All Required Tags | Create Dependencies (must exist before this) | Delete Dependencies (must be deleted before this) |
|---|---|---|---|---|---|---|---|---|
| arch2_vpc_main | AWS::EC2::VPC | C | Tier 2 | N/A | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=processing-orchestration; ResourceGroup=C | none | arch2_private_subnet_a, arch2_private_subnet_b, arch2_eks_cluster_c |
| arch2_private_subnet_a | AWS::EC2::Subnet | C | Tier 2 | N/A | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=processing-orchestration; ResourceGroup=C | arch2_vpc_main | arch2_eks_cluster_c, arch2_rds_primary_c |
| arch2_private_subnet_b | AWS::EC2::Subnet | C | Tier 3 | N/A | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=data-retention; ResourceGroup=C | arch2_vpc_main | arch2_eks_cluster_c, arch2_rds_primary_c |
| arch2_eks_cluster_c | AWS::EKS::Cluster | C | Tier 2 | EKS.PUBLIC_ENDPOINT | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=processing-orchestration; ResourceGroup=C | arch2_private_subnet_a, arch2_private_subnet_b | none |
| arch2_rds_primary_c | AWS::RDS::DBInstance | C | Tier 3 | RDS.PUBLIC_ACCESS, RDS.ENCRYPTION | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=data-retention; ResourceGroup=C | arch2_private_subnet_a, arch2_private_subnet_b | none |
| arch2_securityhub_account_c | securityhub:EnableSecurityHub (account setting) | C | Tier 4 | SecurityHub.1 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=governance-admin; ResourceGroup=C | none | none |
| arch2_guardduty_detector_c | AWS::GuardDuty::Detector | C | Tier 4 | GuardDuty.1 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=governance-admin; ResourceGroup=C | none | none |
| arch2_cloudtrail_main_c | AWS::CloudTrail::Trail | C | Tier 4 | CloudTrail.1 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=governance-admin; ResourceGroup=C | arch2_cloudtrail_logs_bucket_c | none |
| arch2_cloudtrail_logs_bucket_c | AWS::S3::Bucket | C | Tier 3 | CloudTrail.1 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=data-retention; ResourceGroup=C | none | arch2_cloudtrail_main_c |
| arch2_config_bucket_c | AWS::S3::Bucket | C | Tier 3 | Config.1 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=data-retention; ResourceGroup=C | none | arch2_config_delivery_channel_c |
| arch2_config_recorder_c | AWS::Config::ConfigurationRecorder | C | Tier 4 | Config.1 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=governance-admin; ResourceGroup=C | none | arch2_config_delivery_channel_c |
| arch2_config_delivery_channel_c | AWS::Config::DeliveryChannel | C | Tier 4 | Config.1 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=governance-admin; ResourceGroup=C | arch2_config_bucket_c, arch2_config_recorder_c | none |
| arch2_ssm_sharing_block_c | ssm:UpdateServiceSetting (account setting) | C | Tier 4 | SSM.7 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=governance-admin; ResourceGroup=C | none | none |
| arch2_ebs_default_encryption_c | ec2:EnableEbsEncryptionByDefault + ec2:ModifyEbsDefaultKmsKeyId (account setting) | C | Tier 4 | EC2.7 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=governance-admin; ResourceGroup=C | none | none |
| arch2_snapshot_block_public_access_c | AWS::EC2::SnapshotBlockPublicAccess | C | Tier 4 | EC2.182 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=governance-admin; ResourceGroup=C | none | none |
| arch2_root_credentials_state_c | AWS account root principal (existing account entity) | C | Tier 4 | IAM.4 | none | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=governance-admin; ResourceGroup=C | none | none |
| arch2_shared_compute_role_a3 | AWS::IAM::Role | A | Tier 2 | IAM.4 | BlastRadiusTest=iam-multi-principal | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=processing-orchestration; ResourceGroup=A; BlastRadiusTest=iam-multi-principal | none | none |
| arch2_mixed_policy_role_b3 | AWS::IAM::Role | B | Tier 4 | IAM.4 | ContextTest=inline-plus-managed | Project=AWS-Security-Autopilot; Environment=prod-readiness; ManagedBy=aws-cli; Architecture=architecture-2; Tier=governance-admin; ResourceGroup=B; ContextTest=inline-plus-managed | none | none |

SECTION 3 — SHARED VARIABLES BLOCK
| Variable Name | Value or Placeholder | Used by |
|--------------|---------------------|---------|
| ACCOUNT_ID | `<YOUR_ACCOUNT_ID_HERE>` | All account-scoped resources |
| AWS_REGION | `<YOUR_AWS_REGION_HERE>` | All regional resources |
| ARCH1_VPC_MAIN_NAME | `arch1_vpc_main` | Architecture 1 |
| ARCH1_PUBLIC_SUBNET_A_NAME | `arch1_public_subnet_a` | Architecture 1 |
| ARCH1_PRIVATE_SUBNET_A_NAME | `arch1_private_subnet_a` | Architecture 1 |
| ARCH1_SG_APP_B2_NAME | `arch1_sg_app_b2` | Architecture 1 |
| ARCH1_SG_DEPENDENCY_A2_NAME | `arch1_sg_dependency_a2` | Architecture 1 |
| ARCH1_SG_REFERENCE_A2_NAME | `arch1_sg_reference_a2` | Architecture 1 |
| ARCH1_APP_SERVER_A2_NAME | `arch1_app_server_a2` | Architecture 1 |
| ARCH1_CLAIMS_DB_A2_NAME | `arch1_claims_db_a2` | Architecture 1 |
| ARCH1_BUCKET_WEBSITE_A1_NAME | `arch1_bucket_website_a1` | Architecture 1 |
| ARCH1_BUCKET_POLICY_WEBSITE_A1_NAME | `arch1_bucket_policy_website_a1` | Architecture 1 |
| ARCH1_BUCKET_EVIDENCE_B1_NAME | `arch1_bucket_evidence_b1` | Architecture 1 |
| ARCH1_BUCKET_POLICY_EVIDENCE_B1_NAME | `arch1_bucket_policy_evidence_b1` | Architecture 1 |
| ARCH1_BUCKET_PAB_EVIDENCE_B1_NAME | `arch1_bucket_pab_evidence_b1` | Architecture 1 |
| ARCH1_BUCKET_INGEST_C_NAME | `arch1_bucket_ingest_c` | Architecture 1 |
| ARCH1_BUCKET_POLICY_INGEST_C_NAME | `arch1_bucket_policy_ingest_c` | Architecture 1 |
| ARCH1_BUCKET_LOGGING_TARGET_C_NAME | `arch1_bucket_logging_target_c` | Architecture 1 |
| ARCH1_ACCOUNT_PAB_C_NAME | `arch1_account_pab_c` | Architecture 1 |
| ARCH1_WEB_INGEST_SERVICE_NAME | `arch1_web_ingest_service` | Architecture 1 |
| ARCH2_VPC_MAIN_NAME | `arch2_vpc_main` | Architecture 2 |
| ARCH2_PRIVATE_SUBNET_A_NAME | `arch2_private_subnet_a` | Architecture 2 |
| ARCH2_PRIVATE_SUBNET_B_NAME | `arch2_private_subnet_b` | Architecture 2 |
| ARCH2_EKS_CLUSTER_C_NAME | `arch2_eks_cluster_c` | Architecture 2 |
| ARCH2_RDS_PRIMARY_C_NAME | `arch2_rds_primary_c` | Architecture 2 |
| ARCH2_SECURITYHUB_ACCOUNT_C_NAME | `arch2_securityhub_account_c` | Architecture 2 |
| ARCH2_GUARDDUTY_DETECTOR_C_NAME | `arch2_guardduty_detector_c` | Architecture 2 |
| ARCH2_CLOUDTRAIL_MAIN_C_NAME | `arch2_cloudtrail_main_c` | Architecture 2 |
| ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_NAME | `arch2_cloudtrail_logs_bucket_c` | Architecture 2 |
| ARCH2_CONFIG_BUCKET_C_NAME | `arch2_config_bucket_c` | Architecture 2 |
| ARCH2_CONFIG_RECORDER_C_NAME | `arch2_config_recorder_c` | Architecture 2 |
| ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME | `arch2_config_delivery_channel_c` | Architecture 2 |
| ARCH2_SSM_SHARING_BLOCK_C_NAME | `arch2_ssm_sharing_block_c` | Architecture 2 |
| ARCH2_EBS_DEFAULT_ENCRYPTION_C_NAME | `arch2_ebs_default_encryption_c` | Architecture 2 |
| ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_NAME | `arch2_snapshot_block_public_access_c` | Architecture 2 |
| ARCH2_ROOT_CREDENTIALS_STATE_C_NAME | `arch2_root_credentials_state_c` | Architecture 2 |
| ARCH2_SHARED_COMPUTE_ROLE_A3_NAME | `arch2_shared_compute_role_a3` | Architecture 2 |
| ARCH2_MIXED_POLICY_ROLE_B3_NAME | `arch2_mixed_policy_role_b3` | Architecture 2 |
| ARCH1_VPC_CIDR | `10.10.0.0/16` | Architecture 1 VPC |
| ARCH1_PUBLIC_SUBNET_A_CIDR | `10.10.1.0/24` | Architecture 1 subnet |
| ARCH1_PRIVATE_SUBNET_A_CIDR | `10.10.11.0/24` | Architecture 1 subnet |
| ARCH2_VPC_CIDR | `10.20.0.0/16` | Architecture 2 VPC |
| ARCH2_PRIVATE_SUBNET_A_CIDR | `10.20.11.0/24` | Architecture 2 subnet |
| ARCH2_PRIVATE_SUBNET_B_CIDR | `10.20.12.0/24` | Architecture 2 subnet |
| SSH_PORT | `22` | SG misconfiguration test |
| HTTPS_PORT | `443` | SG legitimate rule |
| POSTGRES_PORT | `5432` | SG legitimate rule |
| APP_PORT | `8080` | SG legitimate rule |
| PUBLIC_CIDR_ANY | `0.0.0.0/0` | Public exposure test |
| INTERNAL_VPC_CIDR | `10.0.0.0/16` | Legitimate internal ingress |
| ADMIN_HOST_CIDR | `203.0.113.10/32` | Legitimate point ingress |
| B1_DATA_PIPELINE_ROLE_ARN_PATTERN | `arn:aws:iam::<ACCOUNT_ID>:role/DataPipelineRole` | B1 bucket policy statement |
| B1_DATA_PIPELINE_ROLE_ARN_VALUE | `arn:aws:iam::111122223333:role/DataPipelineRole` | B1 bucket policy statement |
| B1_CROSS_ACCOUNT_ID | `123456789012` | B1 bucket policy statement |
| TAG_PROJECT | `Project=AWS-Security-Autopilot` | All resources |
| TAG_ENVIRONMENT | `Environment=prod-readiness` | All resources |
| TAG_MANAGED_BY | `ManagedBy=aws-cli` | All resources |
| TAG_ARCH1 | `Architecture=architecture-1` | Architecture 1 resources |
| TAG_ARCH2 | `Architecture=architecture-2` | Architecture 2 resources |
| TAG_GROUP_A1 | `BlastRadiusTest=website-hosting` | A1 resources |
| TAG_GROUP_A2 | `BlastRadiusTest=sg-dependency-chain` | A2 resources |
| TAG_GROUP_A3 | `BlastRadiusTest=iam-multi-principal` | A3 resources |
| TAG_GROUP_B1 | `ContextTest=existing-complex-policy` | B1 resources |
| TAG_GROUP_B2 | `ContextTest=mixed-sg-rules` | B2 resources |
| TAG_GROUP_B3 | `ContextTest=inline-plus-managed` | B3 resources |

SECTION 4 — DEPENDENCY ORDER
ARCHITECTURE 1 CREATE ORDER
arch1_vpc_main — depends on: none — AWS::EC2::VPC
arch1_public_subnet_a — depends on: arch1_vpc_main — AWS::EC2::Subnet
arch1_private_subnet_a — depends on: arch1_vpc_main — AWS::EC2::Subnet
arch1_sg_app_b2 — depends on: arch1_vpc_main — AWS::EC2::SecurityGroup
arch1_sg_dependency_a2 — depends on: arch1_vpc_main — AWS::EC2::SecurityGroup
arch1_sg_reference_a2 — depends on: arch1_vpc_main, arch1_sg_dependency_a2 — AWS::EC2::SecurityGroup
arch1_bucket_website_a1 — depends on: none — AWS::S3::Bucket
arch1_bucket_policy_website_a1 — depends on: arch1_bucket_website_a1 — AWS::S3::BucketPolicy
arch1_bucket_evidence_b1 — depends on: none — AWS::S3::Bucket
arch1_bucket_policy_evidence_b1 — depends on: arch1_bucket_evidence_b1 — AWS::S3::BucketPolicy
arch1_bucket_pab_evidence_b1 — depends on: arch1_bucket_evidence_b1 — AWS::S3::BucketPublicAccessBlock
arch1_bucket_logging_target_c — depends on: none — AWS::S3::Bucket
arch1_bucket_ingest_c — depends on: none — AWS::S3::Bucket
arch1_bucket_policy_ingest_c — depends on: arch1_bucket_ingest_c — AWS::S3::BucketPolicy
arch1_app_server_a2 — depends on: arch1_public_subnet_a, arch1_sg_dependency_a2 — AWS::EC2::Instance
arch1_claims_db_a2 — depends on: arch1_private_subnet_a, arch1_sg_dependency_a2 — AWS::RDS::DBInstance
arch1_account_pab_c — depends on: none — s3control:PutPublicAccessBlock
arch1_web_ingest_service — depends on: arch1_public_subnet_a, arch1_sg_app_b2 — AWS::ECS::Service

ARCHITECTURE 1 DELETE ORDER (reverse dependency)
arch1_web_ingest_service — must delete before: arch1_sg_app_b2, arch1_public_subnet_a — AWS::ECS::Service
arch1_app_server_a2 — must delete before: arch1_sg_dependency_a2, arch1_public_subnet_a — AWS::EC2::Instance
arch1_claims_db_a2 — must delete before: arch1_sg_dependency_a2, arch1_private_subnet_a — AWS::RDS::DBInstance
arch1_sg_reference_a2 — must delete before: arch1_sg_dependency_a2, arch1_vpc_main — AWS::EC2::SecurityGroup
arch1_bucket_policy_website_a1 — must delete before: arch1_bucket_website_a1 — AWS::S3::BucketPolicy
arch1_bucket_policy_evidence_b1 — must delete before: arch1_bucket_evidence_b1 — AWS::S3::BucketPolicy
arch1_bucket_pab_evidence_b1 — must delete before: arch1_bucket_evidence_b1 — AWS::S3::BucketPublicAccessBlock
arch1_bucket_policy_ingest_c — must delete before: arch1_bucket_ingest_c — AWS::S3::BucketPolicy
arch1_sg_app_b2 — must delete before: arch1_vpc_main — AWS::EC2::SecurityGroup
arch1_sg_dependency_a2 — must delete before: arch1_vpc_main — AWS::EC2::SecurityGroup
arch1_public_subnet_a — must delete before: arch1_vpc_main — AWS::EC2::Subnet
arch1_private_subnet_a — must delete before: arch1_vpc_main — AWS::EC2::Subnet
arch1_bucket_website_a1 — must delete before: none — AWS::S3::Bucket
arch1_bucket_evidence_b1 — must delete before: none — AWS::S3::Bucket
arch1_bucket_ingest_c — must delete before: none — AWS::S3::Bucket
arch1_bucket_logging_target_c — must delete before: none — AWS::S3::Bucket
arch1_account_pab_c — must delete before: none — s3control:PutPublicAccessBlock
arch1_vpc_main — must delete before: none — AWS::EC2::VPC

ARCHITECTURE 2 CREATE ORDER
arch2_vpc_main — depends on: none — AWS::EC2::VPC
arch2_private_subnet_a — depends on: arch2_vpc_main — AWS::EC2::Subnet
arch2_private_subnet_b — depends on: arch2_vpc_main — AWS::EC2::Subnet
arch2_cloudtrail_logs_bucket_c — depends on: none — AWS::S3::Bucket
arch2_config_bucket_c — depends on: none — AWS::S3::Bucket
arch2_securityhub_account_c — depends on: none — securityhub:EnableSecurityHub
arch2_guardduty_detector_c — depends on: none — AWS::GuardDuty::Detector
arch2_config_recorder_c — depends on: none — AWS::Config::ConfigurationRecorder
arch2_config_delivery_channel_c — depends on: arch2_config_bucket_c, arch2_config_recorder_c — AWS::Config::DeliveryChannel
arch2_cloudtrail_main_c — depends on: arch2_cloudtrail_logs_bucket_c — AWS::CloudTrail::Trail
arch2_ssm_sharing_block_c — depends on: none — ssm:UpdateServiceSetting
arch2_ebs_default_encryption_c — depends on: none — ec2:EnableEbsEncryptionByDefault + ec2:ModifyEbsDefaultKmsKeyId
arch2_snapshot_block_public_access_c — depends on: none — AWS::EC2::SnapshotBlockPublicAccess
arch2_root_credentials_state_c — depends on: none — AWS account root principal (existing account entity)
arch2_shared_compute_role_a3 — depends on: none — AWS::IAM::Role
arch2_mixed_policy_role_b3 — depends on: none — AWS::IAM::Role
arch2_rds_primary_c — depends on: arch2_private_subnet_a, arch2_private_subnet_b — AWS::RDS::DBInstance
arch2_eks_cluster_c — depends on: arch2_private_subnet_a, arch2_private_subnet_b — AWS::EKS::Cluster

ARCHITECTURE 2 DELETE ORDER
arch2_eks_cluster_c — must delete before: arch2_private_subnet_a, arch2_private_subnet_b — AWS::EKS::Cluster
arch2_rds_primary_c — must delete before: arch2_private_subnet_a, arch2_private_subnet_b — AWS::RDS::DBInstance
arch2_cloudtrail_main_c — must delete before: arch2_cloudtrail_logs_bucket_c — AWS::CloudTrail::Trail
arch2_config_delivery_channel_c — must delete before: arch2_config_bucket_c, arch2_config_recorder_c — AWS::Config::DeliveryChannel
arch2_private_subnet_a — must delete before: arch2_vpc_main — AWS::EC2::Subnet
arch2_private_subnet_b — must delete before: arch2_vpc_main — AWS::EC2::Subnet
arch2_config_recorder_c — must delete before: none — AWS::Config::ConfigurationRecorder
arch2_cloudtrail_logs_bucket_c — must delete before: none — AWS::S3::Bucket
arch2_config_bucket_c — must delete before: none — AWS::S3::Bucket
arch2_securityhub_account_c — must delete before: none — securityhub:EnableSecurityHub
arch2_guardduty_detector_c — must delete before: none — AWS::GuardDuty::Detector
arch2_ssm_sharing_block_c — must delete before: none — ssm:UpdateServiceSetting
arch2_ebs_default_encryption_c — must delete before: none — ec2:EnableEbsEncryptionByDefault + ec2:ModifyEbsDefaultKmsKeyId
arch2_snapshot_block_public_access_c — must delete before: none — AWS::EC2::SnapshotBlockPublicAccess
arch2_root_credentials_state_c — must delete before: none — AWS account root principal (existing account entity)
arch2_shared_compute_role_a3 — must delete before: none — AWS::IAM::Role
arch2_mixed_policy_role_b3 — must delete before: none — AWS::IAM::Role
arch2_vpc_main — must delete before: none — AWS::EC2::VPC

SECTION 5 — ADVERSARIAL RESOURCE REGISTRY
| Resource Name | Architecture | Series | Tag | Group A Name | Group B Name | Group C Name | Reset action needed after remediation |
|---|---|---|---|---|---|---|---|
| arch1_bucket_website_a1 | Architecture 1 | A | BlastRadiusTest=website-hosting | arch1_bucket_website_a1 | arch1_bucket_evidence_b1 | arch1_bucket_ingest_c | Restore website-hosting misconfiguration state (public website path) after validation run. |
| arch1_sg_dependency_a2 | Architecture 1 | A | BlastRadiusTest=sg-dependency-chain | arch1_sg_dependency_a2 | arch1_sg_app_b2 | arch1_vpc_main | Recreate permissive SSH rule and SG reference chain after remediation proof completes. |
| arch2_shared_compute_role_a3 | Architecture 2 | A | BlastRadiusTest=iam-multi-principal | arch2_shared_compute_role_a3 | arch2_mixed_policy_role_b3 | arch2_root_credentials_state_c | Reapply broad inline-permission test state on shared role after proof run. |
| arch1_bucket_evidence_b1 | Architecture 1 | B | ContextTest=existing-complex-policy | arch1_bucket_website_a1 | arch1_bucket_evidence_b1 | arch1_bucket_ingest_c | Re-disable bucket public access block while preserving legitimate policy statements for next adversarial cycle. |
| arch1_sg_app_b2 | Architecture 1 | B | ContextTest=mixed-sg-rules | arch1_sg_dependency_a2 | arch1_sg_app_b2 | arch1_vpc_main | Reintroduce only the public SSH rule (`22` from `0.0.0.0/0`) for repeatable proof tests. |
| arch2_mixed_policy_role_b3 | Architecture 2 | B | ContextTest=inline-plus-managed | arch2_shared_compute_role_a3 | arch2_mixed_policy_role_b3 | arch2_root_credentials_state_c | Re-add wildcard inline policy while preserving managed-policy attachments for future validation runs. |

SECTION 6 — PR PROOF VALIDATION TARGETS
| Architecture | Series (A or B) | Resource Name |
|---|---|---|
| Architecture 1 | A | arch1_sg_dependency_a2 |
| Architecture 1 | B | arch1_bucket_evidence_b1 |
| Architecture 2 | A | arch2_shared_compute_role_a3 |
| Architecture 2 | B | arch2_mixed_policy_role_b3 |

SECTION 7 — VALIDATION FLAGS
- A resource type cannot be created with AWS CLI v2 alone: `arch2_root_credentials_state_c` (`AWS account root principal (existing account entity)` is pre-existing and not creatable by CLI as a deployable resource).
