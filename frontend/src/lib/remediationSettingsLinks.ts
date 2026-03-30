export interface RemediationSettingsLink {
  fieldId: string;
  href: string;
  key: string;
  label: string;
}

const FIELD_IDS = {
  approved_admin_cidrs: 'approved-admin-cidrs',
  approved_bastion_security_group_ids: 'approved-bastion-security-group-ids',
  cloudtrail_default_bucket_name: 'cloudtrail-default-bucket-name',
  cloudtrail_default_kms_key_arn: 'cloudtrail-default-kms-key-arn',
  config_default_bucket_name: 'config-default-bucket-name',
  config_default_kms_key_arn: 'config-default-kms-key-arn',
  config_delivery_mode: 'config-delivery-mode',
  s3_access_logs_default_target_bucket_name: 's3-access-logs-default-target-bucket-name',
  s3_encryption_mode: 's3-encryption-mode',
  s3_encryption_kms_key_arn: 's3-encryption-kms-key-arn',
} as const;

const SETTINGS_BASE_HREF = '/settings?tab=remediation-defaults';

type LinkDefinition = {
  fieldId: string;
  label: string;
};

const LINK_DEFINITIONS: Record<string, LinkDefinition> = {
  approved_admin_cidrs: {
    fieldId: FIELD_IDS.approved_admin_cidrs,
    label: 'Add approved admin CIDRs',
  },
  approved_bastion_security_group_ids: {
    fieldId: FIELD_IDS.approved_bastion_security_group_ids,
    label: 'Add approved bastion security groups',
  },
  'cloudtrail.default_bucket_name': {
    fieldId: FIELD_IDS.cloudtrail_default_bucket_name,
    label: 'Configure CloudTrail bucket defaults',
  },
  cloudtrail_default_bucket_name: {
    fieldId: FIELD_IDS.cloudtrail_default_bucket_name,
    label: 'Configure CloudTrail bucket defaults',
  },
  'cloudtrail.default_kms_key_arn': {
    fieldId: FIELD_IDS.cloudtrail_default_kms_key_arn,
    label: 'Configure CloudTrail KMS defaults',
  },
  cloudtrail_default_kms_key_arn: {
    fieldId: FIELD_IDS.cloudtrail_default_kms_key_arn,
    label: 'Configure CloudTrail KMS defaults',
  },
  'config.default_bucket_name': {
    fieldId: FIELD_IDS.config_default_bucket_name,
    label: 'Configure AWS Config bucket defaults',
  },
  config_delivery_bucket_name: {
    fieldId: FIELD_IDS.config_default_bucket_name,
    label: 'Configure AWS Config bucket defaults',
  },
  'config.default_kms_key_arn': {
    fieldId: FIELD_IDS.config_default_kms_key_arn,
    label: 'Configure AWS Config KMS defaults',
  },
  'config.delivery_mode': {
    fieldId: FIELD_IDS.config_delivery_mode,
    label: 'Choose AWS Config delivery mode',
  },
  's3_access_logs.default_target_bucket_name': {
    fieldId: FIELD_IDS.s3_access_logs_default_target_bucket_name,
    label: 'Configure S3 access log target defaults',
  },
  's3_encryption.mode': {
    fieldId: FIELD_IDS.s3_encryption_mode,
    label: 'Choose S3 encryption default',
  },
  's3_encryption.kms_key_arn': {
    fieldId: FIELD_IDS.s3_encryption_kms_key_arn,
    label: 'Configure S3 KMS default',
  },
} as const;

export function getRemediationSettingsFieldIds() {
  return FIELD_IDS;
}

export function getRemediationSettingsLink(key: string | null | undefined): RemediationSettingsLink | null {
  const normalizedKey = (key || '').trim();
  if (!normalizedKey) return null;
  const definition = LINK_DEFINITIONS[normalizedKey];
  if (!definition) return null;
  return {
    fieldId: definition.fieldId,
    href: `${SETTINGS_BASE_HREF}#${definition.fieldId}`,
    key: normalizedKey,
    label: definition.label,
  };
}
