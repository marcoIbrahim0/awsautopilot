# S3.2 migration variant (CloudFront + OAC + private S3) - Action: 52afd4d2-3738-416e-b37b-fbe110dba3fe
# Remediation for: S3 general purpose buckets should block public write access
# Account: 696505809372 | Region: eu-north-1 | Bucket: wi1-noncurrent-lifecycle-696505809372-20260330003655
# Control: S3.2

locals {
  bucket_name = "wi1-noncurrent-lifecycle-696505809372-20260330003655"
  # Include action/run-level entropy to avoid account-wide OAC name collisions on reruns.
  oac_name_seed = "${local.bucket_name}-52afd4d23738416eb37bfbe110dba3fe-20260401004419819313"
  oac_name      = substr("security-autopilot-oac-${substr(md5(local.oac_name_seed), 0, 12)}", 0, 64)
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

variable "additional_read_principal_arns" {
  type        = list(string)
  description = "Optional IAM principal ARNs that still require direct S3 GetObject access."
  default     = []
}

data "aws_s3_bucket" "target" {
  bucket = local.bucket_name
}

data "aws_s3_bucket_policy" "existing" {
  bucket = local.bucket_name
}

locals {
  existing_policy_document = try(
    jsondecode(data.aws_s3_bucket_policy.existing.policy),
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
}

resource "aws_cloudfront_origin_access_control" "security_autopilot" {
  name                              = local.oac_name
  description                       = "OAC for Security Autopilot remediation"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "security_autopilot" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Security Autopilot migration for ${local.bucket_name}"
  default_root_object = var.default_root_object
  price_class         = var.price_class

  origin {
    domain_name              = data.aws_s3_bucket.target.bucket_regional_domain_name
    origin_id                = "s3-${local.bucket_name}"
    origin_access_control_id = aws_cloudfront_origin_access_control.security_autopilot.id
  }

  default_cache_behavior {
    target_origin_id         = "s3-${local.bucket_name}"
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
    resources = ["${data.aws_s3_bucket.target.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.security_autopilot.arn]
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
      resources = ["${data.aws_s3_bucket.target.arn}/*"]
    }
  }
}

resource "aws_s3_bucket_policy" "security_autopilot" {
  bucket = data.aws_s3_bucket.target.id
  policy = data.aws_iam_policy_document.bucket_policy.json
}

resource "aws_s3_bucket_public_access_block" "security_autopilot" {
  bucket = data.aws_s3_bucket.target.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "cloudfront_distribution_id" {
  value       = aws_cloudfront_distribution.security_autopilot.id
  description = "CloudFront distribution ID."
}

output "cloudfront_domain_name" {
  value       = aws_cloudfront_distribution.security_autopilot.domain_name
  description = "Use this domain in clients instead of direct S3 public URLs."
}

output "bucket_name" {
  value       = data.aws_s3_bucket.target.id
  description = "Target S3 bucket migrated to private access via CloudFront OAC."
}
