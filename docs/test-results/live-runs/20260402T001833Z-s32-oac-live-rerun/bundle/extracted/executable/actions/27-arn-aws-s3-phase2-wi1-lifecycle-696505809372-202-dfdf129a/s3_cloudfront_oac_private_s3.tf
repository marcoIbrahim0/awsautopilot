# S3.2 migration variant (CloudFront + OAC + private S3) - Action: dfdf129a-d3ea-4821-8074-e060d7dd92f6
# Remediation for: S3 general purpose buckets should block public read access
# Account: 696505809372 | Region: eu-north-1 | Bucket: phase2-wi1-lifecycle-696505809372-20260329004157
# Control: S3.2

locals {
  bucket_name                         = "phase2-wi1-lifecycle-696505809372-20260329004157"
  remediation_region                  = "eu-north-1"
  expected_bucket_regional_domain_name = "${local.bucket_name}.s3.${local.remediation_region}.amazonaws.com"
  expected_distribution_comment       = "Security Autopilot migration for ${local.bucket_name}"
  expected_origin_id                  = "s3-${local.bucket_name}"
  # Include action/run-level entropy to avoid account-wide OAC name collisions on reruns.
  oac_name_seed                       = "${local.bucket_name}-dfdf129ad3ea48218074e060d7dd92f6-20260402002357689706"
  oac_name                            = substr("security-autopilot-oac-${substr(md5(local.oac_name_seed), 0, 12)}", 0, 64)
}

variable "default_root_object" {
  type        = string
  description = "Default object served by CloudFront at /"
  default     = "index.html"
}

variable "price_class" {
  type        = string
  description = "CloudFront price class"
  default     = "PriceClass_100"
}

variable "cache_policy_id" {
  type        = string
  description = "CloudFront cache policy (Managed-CachingOptimized default)"
  default     = "658327ea-f89d-4fab-a63d-7e88639e58f6"
}

variable "origin_request_policy_id" {
  type        = string
  description = "CloudFront origin request policy (Managed-CORS-S3Origin default)"
  default     = "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf"
}

variable "existing_bucket_policy_json" {
  type        = string
  description = "Optional existing bucket policy JSON to preserve current non-public statements."
  default     = ""
}

variable "create_bucket_if_missing" {
  type        = bool
  description = "When true, create the target bucket with a minimal private baseline before creating CloudFront + OAC."
  default     = true
}

variable "additional_read_principal_arns" {
  type        = list(string)
  description = "Optional IAM principal ARNs that still require direct S3 GetObject access."
  default     = []
}


resource "aws_s3_bucket" "target_bucket" {
  count  = var.create_bucket_if_missing ? 1 : 0
  bucket = local.bucket_name
}

resource "aws_s3_bucket_ownership_controls" "target_bucket" {
  count  = var.create_bucket_if_missing ? 1 : 0
  bucket = aws_s3_bucket.target_bucket[0].id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "target_bucket" {
  count  = var.create_bucket_if_missing ? 1 : 0
  bucket = aws_s3_bucket.target_bucket[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = "alias/aws/s3"
    }
    bucket_key_enabled = true
  }

  depends_on = [aws_s3_bucket_ownership_controls.target_bucket]
}


data "aws_s3_bucket" "existing_target" {
  count  = var.create_bucket_if_missing ? 0 : 1
  bucket = local.bucket_name
}



data "external" "cloudfront_reuse" {
  program = ["python3", "${path.module}/scripts/cloudfront_oac_discovery.py"]

  query = {
    bucket_name                         = local.bucket_name
    expected_bucket_regional_domain_name = local.expected_bucket_regional_domain_name
    expected_distribution_comment       = local.expected_distribution_comment
    expected_oac_name                   = local.oac_name
    expected_origin_id                  = local.expected_origin_id
  }
}

locals {
  target_bucket_id                   = var.create_bucket_if_missing ? aws_s3_bucket.target_bucket[0].id : data.aws_s3_bucket.existing_target[0].id
  target_bucket_arn                  = var.create_bucket_if_missing ? aws_s3_bucket.target_bucket[0].arn : data.aws_s3_bucket.existing_target[0].arn
  target_bucket_regional_domain_name = var.create_bucket_if_missing ? aws_s3_bucket.target_bucket[0].bucket_regional_domain_name : data.aws_s3_bucket.existing_target[0].bucket_regional_domain_name
  existing_policy_document = try(
    var.existing_bucket_policy_json == "" ? { Version = "2012-10-17", Statement = [] } : jsondecode(var.existing_bucket_policy_json),
    {
      Version   = "2012-10-17"
      Statement = []
    }
  )
  existing_policy_id = try(local.existing_policy_document.Id, null)
  existing_policy_statements = try(local.existing_policy_document.Statement, [])
  filtered_existing_policy_statements = [
    for stmt in local.existing_policy_statements : stmt
    if lower(try(tostring(stmt.Sid), "")) != "allowcloudfrontreadonly"
  ]
  filtered_existing_policy_document = merge(
    {
      Version   = try(tostring(local.existing_policy_document.Version), "2012-10-17")
      Statement = local.filtered_existing_policy_statements
    },
    local.existing_policy_id == null ? {} : { Id = local.existing_policy_id }
  )
  cloudfront_reuse_mode = lookup(data.external.cloudfront_reuse.result, "mode", "create")
  reuse_distribution    = local.cloudfront_reuse_mode == "reuse_distribution"
  reuse_oac_only        = local.cloudfront_reuse_mode == "reuse_oac_only"
  reuse_oac             = local.reuse_distribution || local.reuse_oac_only
  effective_oac_id = local.reuse_oac
    ? lookup(data.external.cloudfront_reuse.result, "oac_id", "")
    : aws_cloudfront_origin_access_control.security_autopilot[0].id
  effective_distribution_id = local.reuse_distribution
    ? lookup(data.external.cloudfront_reuse.result, "distribution_id", "")
    : aws_cloudfront_distribution.security_autopilot[0].id
  effective_distribution_arn = local.reuse_distribution
    ? lookup(data.external.cloudfront_reuse.result, "distribution_arn", "")
    : aws_cloudfront_distribution.security_autopilot[0].arn
  effective_distribution_domain_name = local.reuse_distribution
    ? lookup(data.external.cloudfront_reuse.result, "distribution_domain_name", "")
    : aws_cloudfront_distribution.security_autopilot[0].domain_name
}

resource "aws_cloudfront_origin_access_control" "security_autopilot" {
  count                             = local.reuse_oac ? 0 : 1
  name                              = local.oac_name
  description                       = "OAC for Security Autopilot remediation"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "security_autopilot" {
  count               = local.reuse_distribution ? 0 : 1
  enabled             = true
  is_ipv6_enabled     = true
  comment             = local.expected_distribution_comment
  default_root_object = var.default_root_object
  price_class         = var.price_class

  origin {
    domain_name              = local.target_bucket_regional_domain_name
    origin_id                = local.expected_origin_id
    origin_access_control_id = local.effective_oac_id
  }

  default_cache_behavior {
    target_origin_id         = local.expected_origin_id
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS"]
    cached_methods           = ["GET", "HEAD", "OPTIONS"]
    compress                 = true
    cache_policy_id          = var.cache_policy_id
    origin_request_policy_id = var.origin_request_policy_id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

data "aws_iam_policy_document" "bucket_policy" {
  source_policy_documents = [jsonencode(local.filtered_existing_policy_document)]

  statement {
    sid    = "AllowCloudFrontReadOnly"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${local.target_bucket_arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [local.effective_distribution_arn]
    }
  }

  dynamic "statement" {
    for_each = var.additional_read_principal_arns
    content {
      sid    = "AllowAdditionalRead${substr(md5(statement.value), 0, 8)}"
      effect = "Allow"
      principals {
        type        = "AWS"
        identifiers = [statement.value]
      }
      actions   = ["s3:GetObject"]
      resources = ["${local.target_bucket_arn}/*"]
    }
  }
}

resource "aws_s3_bucket_policy" "security_autopilot" {
  bucket = local.target_bucket_id
  policy = data.aws_iam_policy_document.bucket_policy.json
  depends_on = [aws_s3_bucket_ownership_controls.target_bucket]
}

resource "aws_s3_bucket_public_access_block" "security_autopilot" {
  bucket = local.target_bucket_id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "cloudfront_distribution_id" {
  value       = local.effective_distribution_id
  description = "CloudFront distribution ID."
}

output "cloudfront_domain_name" {
  value       = local.effective_distribution_domain_name
  description = "Use this domain in clients instead of direct S3 public URLs."
}

output "bucket_name" {
  value       = local.target_bucket_id
  description = "Target S3 bucket migrated to private access via CloudFront OAC."
}
