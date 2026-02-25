# 07 Architecture Design

This document is the canonical resource design source for deployment-script preparation.

## Architecture Group Semantics

- Group A: blast-radius adversarial resources (A-series) from `07-task4-a-series-resources.md`.
- Group B: context-preservation adversarial resources (B-series) from `07-task5-b-series-resources.md`.
- Group C: baseline production resources required to form complete architecture graphs.

## Global Required Tags

All resources in both architectures must include these baseline tags:

- `Project=AWS-Security-Autopilot`
- `Environment=prod-readiness`
- `ManagedBy=aws-cli`
- `Architecture=architecture-1` or `Architecture=architecture-2`
- `Tier=<tier-name>`
- `ResourceGroup=A|B|C`

## Architecture 1 Resource Inventory (RapidClaims Telehealth Evidence Pipeline)

### Tier labels

- Tier 1: External Intake
- Tier 2: Workflow and Processing
- Tier 3: Data and Retention
- Tier 4: Operations and Access

| Resource Name | AWS Type | Group (A/B/C) | Tier | Control IDs | Adversarial Tag | All Required Tags | Create Dependencies (must exist before this) | Delete Dependencies (must be deleted before this) |
|---|---|---|---|---|---|---|---|---|
| arch1_vpc_main | AWS::EC2::VPC | C | Tier 2 | N/A | none | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=workflow-processing, ResourceGroup=C | none | arch1_public_subnet_a, arch1_private_subnet_a, arch1_sg_app_b2, arch1_sg_dependency_a2, arch1_sg_reference_a2 |
| arch1_public_subnet_a | AWS::EC2::Subnet | C | Tier 1 | N/A | none | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=external-intake, ResourceGroup=C | arch1_vpc_main | arch1_app_server_a2 |
| arch1_private_subnet_a | AWS::EC2::Subnet | C | Tier 3 | N/A | none | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=data-retention, ResourceGroup=C | arch1_vpc_main | arch1_claims_db_a2 |
| arch1_sg_app_b2 | AWS::EC2::SecurityGroup | B | Tier 1 | EC2.53, EC2.13, EC2.18, EC2.19 | ContextTest=mixed-sg-rules | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=external-intake, ResourceGroup=B, ContextTest=mixed-sg-rules | arch1_vpc_main | arch1_web_ingest_service |
| arch1_sg_dependency_a2 | AWS::EC2::SecurityGroup | A | Tier 2 | EC2.53, EC2.13, EC2.18, EC2.19 | BlastRadiusTest=sg-dependency-chain | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=workflow-processing, ResourceGroup=A, BlastRadiusTest=sg-dependency-chain | arch1_vpc_main | arch1_app_server_a2, arch1_claims_db_a2, arch1_sg_reference_a2 |
| arch1_sg_reference_a2 | AWS::EC2::SecurityGroup | A | Tier 2 | EC2.53, EC2.13, EC2.18, EC2.19 | BlastRadiusTest=sg-dependency-chain | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=workflow-processing, ResourceGroup=A, BlastRadiusTest=sg-dependency-chain | arch1_vpc_main, arch1_sg_dependency_a2 | none |
| arch1_app_server_a2 | AWS::EC2::Instance | A | Tier 2 | EC2.53, EC2.13, EC2.18, EC2.19 | BlastRadiusTest=sg-dependency-chain | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=workflow-processing, ResourceGroup=A, BlastRadiusTest=sg-dependency-chain | arch1_public_subnet_a, arch1_sg_dependency_a2 | none |
| arch1_claims_db_a2 | AWS::RDS::DBInstance | A | Tier 3 | EC2.53, EC2.13, EC2.18, EC2.19 | BlastRadiusTest=sg-dependency-chain | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=data-retention, ResourceGroup=A, BlastRadiusTest=sg-dependency-chain | arch1_private_subnet_a, arch1_sg_dependency_a2 | none |
| arch1_bucket_website_a1 | AWS::S3::Bucket | A | Tier 1 | S3.2, S3.3, S3.8, S3.17 | BlastRadiusTest=website-hosting | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=external-intake, ResourceGroup=A, BlastRadiusTest=website-hosting | none | arch1_bucket_policy_website_a1 |
| arch1_bucket_policy_website_a1 | AWS::S3::BucketPolicy | A | Tier 1 | S3.5 | BlastRadiusTest=website-hosting | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=external-intake, ResourceGroup=A, BlastRadiusTest=website-hosting | arch1_bucket_website_a1 | none |
| arch1_bucket_evidence_b1 | AWS::S3::Bucket | B | Tier 3 | S3.2, S3.3, S3.8, S3.17 | ContextTest=existing-complex-policy | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=data-retention, ResourceGroup=B, ContextTest=existing-complex-policy | none | arch1_bucket_policy_evidence_b1, arch1_bucket_pab_evidence_b1 |
| arch1_bucket_policy_evidence_b1 | AWS::S3::BucketPolicy | B | Tier 3 | S3.5 | ContextTest=existing-complex-policy | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=data-retention, ResourceGroup=B, ContextTest=existing-complex-policy | arch1_bucket_evidence_b1 | none |
| arch1_bucket_pab_evidence_b1 | AWS::S3::BucketPublicAccessBlock | B | Tier 3 | S3.2, S3.3, S3.8, S3.17 | ContextTest=existing-complex-policy | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=data-retention, ResourceGroup=B, ContextTest=existing-complex-policy | arch1_bucket_evidence_b1 | none |
| arch1_bucket_ingest_c | AWS::S3::Bucket | C | Tier 3 | S3.2, S3.3, S3.4, S3.8, S3.9, S3.11, S3.15, S3.17 | none | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=data-retention, ResourceGroup=C | none | arch1_bucket_policy_ingest_c, arch1_bucket_logging_target_c |
| arch1_bucket_policy_ingest_c | AWS::S3::BucketPolicy | C | Tier 3 | S3.5 | none | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=data-retention, ResourceGroup=C | arch1_bucket_ingest_c | none |
| arch1_bucket_logging_target_c | AWS::S3::Bucket | C | Tier 3 | S3.9 | none | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=data-retention, ResourceGroup=C | none | none |
| arch1_account_pab_c | s3control:PutPublicAccessBlock (account setting) | C | Tier 4 | S3.1 | none | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=operations-access, ResourceGroup=C | none | none |
| arch1_web_ingest_service | AWS::ECS::Service | C | Tier 1 | N/A | none | Project, Environment, ManagedBy, Architecture=architecture-1, Tier=external-intake, ResourceGroup=C | arch1_public_subnet_a, arch1_sg_app_b2 | none |

## Architecture 2 Resource Inventory (RapidRad Teleradiology Exchange Platform)

### Tier labels

- Tier 1: Access and Ingestion
- Tier 2: Processing and Orchestration
- Tier 3: Data and Retention
- Tier 4: Governance and Administration

| Resource Name | AWS Type | Group (A/B/C) | Tier | Control IDs | Adversarial Tag | All Required Tags | Create Dependencies (must exist before this) | Delete Dependencies (must be deleted before this) |
|---|---|---|---|---|---|---|---|---|
| arch2_vpc_main | AWS::EC2::VPC | C | Tier 2 | N/A | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=processing-orchestration, ResourceGroup=C | none | arch2_private_subnet_a, arch2_private_subnet_b, arch2_eks_cluster_c |
| arch2_private_subnet_a | AWS::EC2::Subnet | C | Tier 2 | N/A | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=processing-orchestration, ResourceGroup=C | arch2_vpc_main | arch2_eks_cluster_c, arch2_rds_primary_c |
| arch2_private_subnet_b | AWS::EC2::Subnet | C | Tier 3 | N/A | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=data-retention, ResourceGroup=C | arch2_vpc_main | arch2_eks_cluster_c, arch2_rds_primary_c |
| arch2_eks_cluster_c | AWS::EKS::Cluster | C | Tier 2 | EKS.PUBLIC_ENDPOINT | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=processing-orchestration, ResourceGroup=C | arch2_private_subnet_a, arch2_private_subnet_b | none |
| arch2_rds_primary_c | AWS::RDS::DBInstance | C | Tier 3 | RDS.PUBLIC_ACCESS, RDS.ENCRYPTION | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=data-retention, ResourceGroup=C | arch2_private_subnet_a, arch2_private_subnet_b | none |
| arch2_securityhub_account_c | securityhub:EnableSecurityHub (account setting) | C | Tier 4 | SecurityHub.1 | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=governance-admin, ResourceGroup=C | none | none |
| arch2_guardduty_detector_c | AWS::GuardDuty::Detector | C | Tier 4 | GuardDuty.1 | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=governance-admin, ResourceGroup=C | none | none |
| arch2_cloudtrail_main_c | AWS::CloudTrail::Trail | C | Tier 4 | CloudTrail.1 | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=governance-admin, ResourceGroup=C | arch2_cloudtrail_logs_bucket_c | none |
| arch2_cloudtrail_logs_bucket_c | AWS::S3::Bucket | C | Tier 3 | CloudTrail.1 | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=data-retention, ResourceGroup=C | none | arch2_cloudtrail_main_c |
| arch2_config_bucket_c | AWS::S3::Bucket | C | Tier 3 | Config.1 | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=data-retention, ResourceGroup=C | none | arch2_config_delivery_channel_c |
| arch2_config_recorder_c | AWS::Config::ConfigurationRecorder | C | Tier 4 | Config.1 | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=governance-admin, ResourceGroup=C | none | none |
| arch2_config_delivery_channel_c | AWS::Config::DeliveryChannel | C | Tier 4 | Config.1 | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=governance-admin, ResourceGroup=C | arch2_config_bucket_c, arch2_config_recorder_c | none |
| arch2_ssm_sharing_block_c | ssm:UpdateServiceSetting (account setting) | C | Tier 4 | SSM.7 | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=governance-admin, ResourceGroup=C | none | none |
| arch2_ebs_default_encryption_c | ec2:EnableEbsEncryptionByDefault + ec2:ModifyEbsDefaultKmsKeyId (account setting) | C | Tier 4 | EC2.7 | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=governance-admin, ResourceGroup=C | none | none |
| arch2_snapshot_block_public_access_c | AWS::EC2::SnapshotBlockPublicAccess | C | Tier 4 | EC2.182 | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=governance-admin, ResourceGroup=C | none | none |
| arch2_root_credentials_state_c | AWS account root principal (existing account entity) | C | Tier 4 | IAM.4 | none | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=governance-admin, ResourceGroup=C | none | none |
| arch2_shared_compute_role_a3 | AWS::IAM::Role | A | Tier 2 | IAM.4 | BlastRadiusTest=iam-multi-principal | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=processing-orchestration, ResourceGroup=A, BlastRadiusTest=iam-multi-principal | none | none |
| arch2_mixed_policy_role_b3 | AWS::IAM::Role | B | Tier 4 | IAM.4 | ContextTest=inline-plus-managed | Project, Environment, ManagedBy, Architecture=architecture-2, Tier=governance-admin, ResourceGroup=B, ContextTest=inline-plus-managed | none | none |

## Shared Variables for Script Generation

| Variable Name | Value | Notes |
|---|---|---|
| ACCOUNT_ID | `<YOUR_ACCOUNT_ID_HERE>` | Required account scope for all account-level settings |
| AWS_REGION | `<YOUR_AWS_REGION_HERE>` | Primary deployment region |
| ARCH1_VPC_CIDR | `10.10.0.0/16` | Architecture 1 VPC CIDR |
| ARCH1_PUBLIC_SUBNET_A_CIDR | `10.10.1.0/24` | Architecture 1 Tier 1 subnet |
| ARCH1_PRIVATE_SUBNET_A_CIDR | `10.10.11.0/24` | Architecture 1 Tier 3 subnet |
| ARCH2_VPC_CIDR | `10.20.0.0/16` | Architecture 2 VPC CIDR |
| ARCH2_PRIVATE_SUBNET_A_CIDR | `10.20.11.0/24` | Architecture 2 subnet A |
| ARCH2_PRIVATE_SUBNET_B_CIDR | `10.20.12.0/24` | Architecture 2 subnet B |
| SSH_PORT | `22` | EC2 SG exposure test port |
| HTTPS_PORT | `443` | Legitimate SG ingress |
| POSTGRES_PORT | `5432` | Legitimate SG ingress |
| APP_PORT | `8080` | Legitimate SG ingress |
| PUBLIC_CIDR_ANY | `0.0.0.0/0` | Misconfiguration test CIDR |
| INTERNAL_VPC_CIDR | `10.0.0.0/16` | Legitimate internal ingress |
| ADMIN_HOST_CIDR | `203.0.113.10/32` | Legitimate point ingress |
| B1_CROSS_ACCOUNT_ID | `123456789012` | B1 policy preservation statement |
| B1_DATA_PIPELINE_ROLE_ARN | `arn:aws:iam::111122223333:role/DataPipelineRole` | B1 policy preservation statement |
| TAG_A1 | `BlastRadiusTest=website-hosting` | Required A1 tag |
| TAG_A2 | `BlastRadiusTest=sg-dependency-chain` | Required A2 tag |
| TAG_A3 | `BlastRadiusTest=iam-multi-principal` | Required A3 tag |
| TAG_B1 | `ContextTest=existing-complex-policy` | Required B1 tag |
| TAG_B2 | `ContextTest=mixed-sg-rules` | Required B2 tag |
| TAG_B3 | `ContextTest=inline-plus-managed` | Required B3 tag |

## Adversarial Resource Placement Registry

| Series | Resource Name | Architecture | Group Name |
|---|---|---|---|
| A | A1 (website-hosting bucket) | Architecture 1 | arch1_bucket_website_a1 |
| A | A2 (SG dependency chain) | Architecture 1 | arch1_sg_dependency_a2 |
| A | A3 (IAM multi-principal role) | Architecture 2 | arch2_shared_compute_role_a3 |
| B | B1 (S3 complex policy) | Architecture 1 | arch1_bucket_evidence_b1 |
| B | B2 (mixed SG rules) | Architecture 1 | arch1_sg_app_b2 |
| B | B3 (inline + managed IAM policy) | Architecture 2 | arch2_mixed_policy_role_b3 |

## PR Proof Validation Targets

Exactly four targets are required (two per architecture, one A-series and one B-series):

| Architecture | Series | Resource Name |
|---|---|---|
| Architecture 1 | A | arch1_sg_dependency_a2 |
| Architecture 1 | B | arch1_bucket_evidence_b1 |
| Architecture 2 | A | arch2_shared_compute_role_a3 |
| Architecture 2 | B | arch2_mixed_policy_role_b3 |

## Control Coverage Resolution Matrix

| Control ID | Architecture | Resource Name |
|---|---|---|
| S3.1 | Architecture 1 | arch1_account_pab_c |
| S3.2 | Architecture 1 | arch1_bucket_ingest_c |
| S3.3 | Architecture 1 | arch1_bucket_ingest_c |
| S3.4 | Architecture 1 | arch1_bucket_ingest_c |
| S3.5 | Architecture 1 | arch1_bucket_policy_ingest_c |
| S3.8 | Architecture 1 | arch1_bucket_ingest_c |
| S3.9 | Architecture 1 | arch1_bucket_logging_target_c |
| S3.11 | Architecture 1 | arch1_bucket_ingest_c |
| S3.15 | Architecture 1 | arch1_bucket_ingest_c |
| S3.17 | Architecture 1 | arch1_bucket_ingest_c |
| EC2.53 | Architecture 1 | arch1_sg_dependency_a2 |
| EC2.13 | Architecture 1 | arch1_sg_dependency_a2 |
| EC2.18 | Architecture 1 | arch1_sg_dependency_a2 |
| EC2.19 | Architecture 1 | arch1_sg_dependency_a2 |
| SecurityHub.1 | Architecture 2 | arch2_securityhub_account_c |
| GuardDuty.1 | Architecture 2 | arch2_guardduty_detector_c |
| CloudTrail.1 | Architecture 2 | arch2_cloudtrail_main_c |
| Config.1 | Architecture 2 | arch2_config_delivery_channel_c |
| SSM.7 | Architecture 2 | arch2_ssm_sharing_block_c |
| EC2.7 | Architecture 2 | arch2_ebs_default_encryption_c |
| EC2.182 | Architecture 2 | arch2_snapshot_block_public_access_c |
| IAM.4 | Architecture 2 | arch2_root_credentials_state_c |
| RDS.PUBLIC_ACCESS | Architecture 2 | arch2_rds_primary_c |
| RDS.ENCRYPTION | Architecture 2 | arch2_rds_primary_c |
| EKS.PUBLIC_ENDPOINT | Architecture 2 | arch2_eks_cluster_c |
