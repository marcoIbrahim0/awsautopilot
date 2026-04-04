# S3.2 migration variant (CloudFront + OAC + private S3) - Action: dda812ab-15c2-482f-8782-ffef1ab0a60d
# Remediation for: S3 general purpose buckets should block public write access
# Account: 696505809372 | Region: eu-north-1 | Bucket: security-autopilot-access-logs-696505809372-s9fix1
# Control: S3.2

locals {
  bucket_name                         = "security-autopilot-access-logs-696505809372-s9fix1"
  remediation_region                  = "eu-north-1"
  expected_bucket_regional_domain_name = "${local.bucket_name}.s3.${local.remediation_region}.amazonaws.com"
  expected_distribution_comment       = "Security Autopilot migration for ${local.bucket_name}"
  expected_origin_id                  = "s3-${local.bucket_name}"
  oac_name                            = "security-autopilot-oac-287f9b08d1aa"
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
  default     = false
}

variable "additional_read_principal_arns" {
  type        = list(string)
  description = "Optional IAM principal ARNs that still require direct S3 GetObject access."
  default     = []
}

variable "cloudfront_reuse_mode" {
  type        = string
  description = "Precomputed CloudFront/OAC reuse mode from the runner preflight."
  default     = "create"
}

variable "reuse_oac_id" {
  type        = string
  description = "Precomputed OAC ID to reuse when cloudfront_reuse_mode requires it."
  default     = ""
}

variable "reuse_distribution_id" {
  type        = string
  description = "Precomputed CloudFront distribution ID to reuse when cloudfront_reuse_mode=reuse_distribution."
  default     = ""
}

variable "reuse_distribution_arn" {
  type        = string
  description = "Precomputed CloudFront distribution ARN to reuse when cloudfront_reuse_mode=reuse_distribution."
  default     = ""
}

variable "reuse_distribution_domain_name" {
  type        = string
  description = "Precomputed CloudFront domain name to reuse when cloudfront_reuse_mode=reuse_distribution."
  default     = ""
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
  cloudfront_reuse_mode = var.cloudfront_reuse_mode
  reuse_distribution    = local.cloudfront_reuse_mode == "reuse_distribution"
  reuse_oac_only        = local.cloudfront_reuse_mode == "reuse_oac_only"
  reuse_oac             = local.reuse_distribution || local.reuse_oac_only
  effective_oac_id = (
    local.reuse_oac
    ? var.reuse_oac_id
    : aws_cloudfront_origin_access_control.security_autopilot[0].id
  )
  effective_distribution_id = (
    local.reuse_distribution
    ? var.reuse_distribution_id
    : aws_cloudfront_distribution.security_autopilot[0].id
  )
  effective_distribution_arn = (
    local.reuse_distribution
    ? var.reuse_distribution_arn
    : aws_cloudfront_distribution.security_autopilot[0].arn
  )
  effective_distribution_domain_name = (
    local.reuse_distribution
    ? var.reuse_distribution_domain_name
    : aws_cloudfront_distribution.security_autopilot[0].domain_name
  )
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
