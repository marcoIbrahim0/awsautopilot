RAW ID REGISTRY EXTRACTION
| ID Value | ID Type | Maps To | Source File | Source Location |
|---------|---------|---------|-------------|----------------|
| S3.1 | control | action_type `s3_block_public_access` (AWS standard control format) | backend/services/control_scope.py | line 54 |
| SecurityHub.1 | control | action_type `enable_security_hub` (AWS standard control format) | backend/services/control_scope.py | line 61 |
| GuardDuty.1 | control | action_type `enable_guardduty` (AWS standard control format) | backend/services/control_scope.py | line 68 |
| S3.2 | control | action_type `s3_bucket_block_public_access` (AWS standard control format) | backend/services/control_scope.py | line 75 |
| S3.4 | control | action_type `s3_bucket_encryption` (AWS standard control format) | backend/services/control_scope.py | line 82 |
| EC2.53 | control | action_type `sg_restrict_public_ports` (AWS standard control format) | backend/services/control_scope.py | line 89 |
| CloudTrail.1 | control | action_type `cloudtrail_enabled` (AWS standard control format) | backend/services/control_scope.py | line 96 |
| Config.1 | control | action_type `aws_config_enabled` (AWS standard control format) | backend/services/control_scope.py | line 103 |
| SSM.7 | control | action_type `ssm_block_public_sharing` (AWS standard control format) | backend/services/control_scope.py | line 110 |
| EC2.182 | control | action_type `ebs_snapshot_block_public_access` (AWS standard control format) | backend/services/control_scope.py | line 117 |
| EC2.7 | control | action_type `ebs_default_encryption` (AWS standard control format) | backend/services/control_scope.py | line 124 |
| S3.5 | control | action_type `s3_bucket_require_ssl` (AWS standard control format) | backend/services/control_scope.py | line 131 |
| IAM.4 | control | action_type `iam_root_access_key_absent` (AWS standard control format) | backend/services/control_scope.py | line 138 |
| S3.9 | control | action_type `s3_bucket_access_logging` (AWS standard control format) | backend/services/control_scope.py | line 145 |
| S3.11 | control | action_type `s3_bucket_lifecycle_configuration` (AWS standard control format) | backend/services/control_scope.py | line 152 |
| S3.15 | control | action_type `s3_bucket_encryption_kms` (AWS standard control format) | backend/services/control_scope.py | line 159 |
| S3.3 | control | action_type `s3_bucket_block_public_access` alias (AWS standard control format) | backend/services/control_scope.py | line 173 |
| S3.8 | control | action_type `s3_bucket_block_public_access` alias (AWS standard control format) | backend/services/control_scope.py | line 174 |
| S3.17 | control | action_type `s3_bucket_block_public_access` alias (AWS standard control format) | backend/services/control_scope.py | line 175 |
| EC2.13 | control | action_type `sg_restrict_public_ports` alias (AWS standard control format) | backend/services/control_scope.py | line 178 |
| EC2.19 | control | action_type `sg_restrict_public_ports` alias (AWS standard control format) | backend/services/control_scope.py | line 179 |
| EC2.18 | control | action_type `sg_restrict_public_ports` alias (AWS standard control format) | backend/services/control_scope.py | line 181 |
| s3_block_public_access | action | control_id `S3.1` (string slug) | backend/services/control_scope.py | line 55 |
| enable_security_hub | action | control_id `SecurityHub.1` (string slug) | backend/services/control_scope.py | line 62 |
| enable_guardduty | action | control_id `GuardDuty.1` (string slug) | backend/services/control_scope.py | line 69 |
| s3_bucket_block_public_access | action | control_id `S3.2` (string slug) | backend/services/control_scope.py | line 76 |
| s3_bucket_encryption | action | control_id `S3.4` (string slug) | backend/services/control_scope.py | line 83 |
| sg_restrict_public_ports | action | control_id `EC2.53` (string slug) | backend/services/control_scope.py | line 90 |
| cloudtrail_enabled | action | control_id `CloudTrail.1` (string slug) | backend/services/control_scope.py | line 97 |
| aws_config_enabled | action | control_id `Config.1` (string slug) | backend/services/control_scope.py | line 104 |
| ssm_block_public_sharing | action | control_id `SSM.7` (string slug) | backend/services/control_scope.py | line 111 |
| ebs_snapshot_block_public_access | action | control_id `EC2.182` (string slug) | backend/services/control_scope.py | line 118 |
| ebs_default_encryption | action | control_id `EC2.7` (string slug) | backend/services/control_scope.py | line 125 |
| s3_bucket_require_ssl | action | control_id `S3.5` (string slug) | backend/services/control_scope.py | line 132 |
| iam_root_access_key_absent | action | control_id `IAM.4` (string slug) | backend/services/control_scope.py | line 139 |
| s3_bucket_access_logging | action | control_id `S3.9` (string slug) | backend/services/control_scope.py | line 146 |
| s3_bucket_lifecycle_configuration | action | control_id `S3.11` (string slug) | backend/services/control_scope.py | line 153 |
| s3_bucket_encryption_kms | action | control_id `S3.15` (string slug) | backend/services/control_scope.py | line 160 |
| pr_only | action | default action type for unmapped controls (string slug) | backend/services/control_scope.py | line 209 |
| AuthorizeSecurityGroupIngress | action | `SECURITY_GROUP_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 18 |
| RevokeSecurityGroupIngress | action | `SECURITY_GROUP_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 19 |
| ModifySecurityGroupRules | action | `SECURITY_GROUP_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 20 |
| UpdateSecurityGroupRuleDescriptionsIngress | action | `SECURITY_GROUP_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 21 |
| PutBucketPolicy | action | `S3_BUCKET_POSTURE_EVALUATION_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 27 |
| DeleteBucketPolicy | action | `S3_BUCKET_POSTURE_EVALUATION_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 28 |
| PutBucketAcl | action | `S3_BUCKET_POSTURE_EVALUATION_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 29 |
| PutPublicAccessBlock | action | `S3_BUCKET_POSTURE_EVALUATION_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 30 |
| DeletePublicAccessBlock | action | `S3_BUCKET_POSTURE_EVALUATION_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 31 |
| PutAccountPublicAccessBlock | action | `S3_MANAGEMENT_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 38 |
| DeleteAccountPublicAccessBlock | action | `S3_MANAGEMENT_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 39 |
| PutBucketEncryption | action | `S3_MANAGEMENT_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 40 |
| DeleteBucketEncryption | action | `S3_MANAGEMENT_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 41 |
| EnableSecurityHub | action | `SECURITY_HUB_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 45 |
| CreateDetector | action | `GUARDDUTY_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 47 |
| UpdateDetector | action | `GUARDDUTY_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 47 |
| CreateTrail | action | `CLOUDTRAIL_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 50 |
| UpdateTrail | action | `CLOUDTRAIL_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 50 |
| StartLogging | action | `CLOUDTRAIL_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 50 |
| StopLogging | action | `CLOUDTRAIL_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 50 |
| PutConfigurationRecorder | action | `CONFIG_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 54 |
| PutDeliveryChannel | action | `CONFIG_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 54 |
| StartConfigurationRecorder | action | `CONFIG_EVENT_NAMES` allowlist entry (AWS API action name) | backend/services/control_plane_event_allowlist.py | line 54 |
| AuthorizeSecurityGroupIngress | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 132 |
| RevokeSecurityGroupIngress | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 133 |
| ModifySecurityGroupRules | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 134 |
| UpdateSecurityGroupRuleDescriptionsIngress | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 135 |
| PutBucketPolicy | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 136 |
| DeleteBucketPolicy | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 137 |
| PutBucketAcl | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 138 |
| PutPublicAccessBlock | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 139 |
| DeletePublicAccessBlock | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 140 |
| PutAccountPublicAccessBlock | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 141 |
| DeleteAccountPublicAccessBlock | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 142 |
| PutBucketEncryption | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 143 |
| DeleteBucketEncryption | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 144 |
| EnableSecurityHub | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 145 |
| CreateDetector | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 146 |
| UpdateDetector | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 147 |
| CreateTrail | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 148 |
| UpdateTrail | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 149 |
| StartLogging | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 150 |
| StopLogging | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 151 |
| PutConfigurationRecorder | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 152 |
| PutDeliveryChannel | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 153 |
| StartConfigurationRecorder | action | EventBridge `EventPattern.detail.eventName` value (AWS API action name) | infrastructure/cloudformation/control-plane-forwarder-template.yaml | line 154 |
| ARC-008 | architecture_objective | DR architecture objective metadata value (non-runtime) | infrastructure/cloudformation/dr-backup-controls.yaml | line 81 |
| security-autopilot-daily | rule | Backup plan rule name (string slug) | infrastructure/cloudformation/dr-backup-controls.yaml | line 109 |
| security-autopilot-tagged | rule | Backup selection name (string slug) | infrastructure/cloudformation/dr-backup-controls.yaml | line 136 |
| BackupRestoreActions | unknown | IAM policy `Sid` identifier (string slug) | infrastructure/cloudformation/dr-backup-controls.yaml | line 160 |
| RdsRestoreActions | unknown | IAM policy `Sid` identifier (string slug) | infrastructure/cloudformation/dr-backup-controls.yaml | line 172 |
| SupportingRestoreActions | unknown | IAM policy `Sid` identifier (string slug) | infrastructure/cloudformation/dr-backup-controls.yaml | line 185 |
| AllowListedIpv4 | rule | WAF rule `Name` (string slug) | infrastructure/cloudformation/edge-protection.yaml | line 100 |
| AWSManagedCommonRuleSet | rule | WAF rule `Name` (string slug) | infrastructure/cloudformation/edge-protection.yaml | line 112 |
| AWSManagedRulesCommonRuleSet | rule | Managed rule group `Name` (AWS standard format) | infrastructure/cloudformation/edge-protection.yaml | line 119 |
| AWSManagedKnownBadInputs | rule | WAF rule `Name` (string slug) | infrastructure/cloudformation/edge-protection.yaml | line 124 |
| AWSManagedRulesKnownBadInputsRuleSet | rule | Managed rule group `Name` (AWS standard format) | infrastructure/cloudformation/edge-protection.yaml | line 131 |
| IPAddressRateLimit | rule | WAF rule `Name` (string slug) | infrastructure/cloudformation/edge-protection.yaml | line 136 |
| EC2.53 | control | `control_preference` first token (AWS standard control format) | scripts/config/no_ui_pr_bundle_agent.example.json | line 5 (`$.control_preference`) |
| S3.2 | control | `control_preference` second token (AWS standard control format) | scripts/config/no_ui_pr_bundle_agent.example.json | line 5 (`$.control_preference`) |

Files read (with line counts):
- docs/prod-readiness/06-task1-file-map.md — 244
- backend/services/control_plane_event_allowlist.py — 64
- backend/services/control_scope.py — 254
- backend/config.py — 502
- backend/workers/config.py — 20
- infrastructure/cloudformation/control-plane-forwarder-template.yaml — 221
- infrastructure/cloudformation/dr-backup-controls.yaml — 257
- infrastructure/cloudformation/read-role-template.yaml — 328
- infrastructure/cloudformation/reconcile-scheduler-template.yaml — 229
- infrastructure/cloudformation/write-role-template.yaml — 295
- infrastructure/cloudformation/edge-protection.yaml — 233
- infrastructure/cloudformation/saas-ecs-dev.yaml — 688
- infrastructure/cloudformation/saas-serverless-build.yaml — 148
- infrastructure/cloudformation/saas-serverless-httpapi.yaml — 640
- infrastructure/cloudformation/sqs-queues.yaml — 841
- scripts/config/no_ui_pr_bundle_agent.example.json — 20

Registry candidate files with no explicit control/rule/check/action IDs found:
- backend/config.py
- backend/workers/config.py
- infrastructure/cloudformation/read-role-template.yaml
- infrastructure/cloudformation/reconcile-scheduler-template.yaml
- infrastructure/cloudformation/write-role-template.yaml
- infrastructure/cloudformation/saas-ecs-dev.yaml
- infrastructure/cloudformation/saas-serverless-build.yaml
- infrastructure/cloudformation/saas-serverless-httpapi.yaml
- infrastructure/cloudformation/sqs-queues.yaml

Output file written: docs/prod-readiness/06-task4-raw-id-registries.md
