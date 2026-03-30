# S3.2 website migration variant (CloudFront + private S3 + Route53) - Action: 352ac9b2-d343-40ac-b427-4c4f285615ef
# Remediation for: S3 general purpose buckets should block public access
# Account: 696505809372 | Region: eu-north-1 | Bucket: security-autopilot-w6-envready-s311-review-696505809372
# Control: S3.2

locals {
  bucket_name               = "security-autopilot-w6-envready-s311-review-696505809372"
  remediation_region        = "eu-north-1"
  oac_name_seed             = "${local.bucket_name}-352ac9b2d34340acb4274c4f285615ef-20260329203717576271"
  oac_name                  = substr("security-autopilot-oac-${substr(md5(local.oac_name_seed), 0, 12)}", 0, 64)
}

variable "aliases" {
  type        = list(string)
  description = "Route53 hostnames that should resolve to the CloudFront distribution."
  default     = ["wi5-gate3-696505809372.net"]
}

variable "route53_hosted_zone_id" {
  type        = string
  description = "Route53 hosted zone ID that owns the aliases."
  default     = "Z089211911JQN783YLH5I"
}

variable "acm_certificate_arn" {
  type        = string
  description = "CloudFront viewer certificate ARN (must be in us-east-1)."
  default     = "arn:aws:acm:us-east-1:696505809372:certificate/e24f54d8-3a83-4de9-88d4-1dcc3cb9b8eb"
}

variable "price_class" {
  type        = string
  description = "CloudFront price class."
  default     = "PriceClass_100"
}

variable "default_root_object" {
  type        = string
  description = "Default root object translated from the captured S3 website IndexDocument."
  default     = "index.html"
}

variable "error_document_key" {
  type        = string
  description = "Optional error document key translated from the captured S3 website configuration."
  default     = ""
}

variable "existing_bucket_website_configuration_json" {
  type        = string
  description = "Captured S3 website configuration JSON for rollback documentation."
}

data "aws_s3_bucket" "target" {
  bucket = local.bucket_name
}

resource "aws_cloudfront_origin_access_control" "security_autopilot" {
  name                              = local.oac_name
  description                       = "OAC for Security Autopilot website migration"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "security_autopilot" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Security Autopilot website migration for ${local.bucket_name}"
  aliases             = var.aliases
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
    cache_policy_id          = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    origin_request_policy_id = "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.acm_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

variable "existing_bucket_policy_json" {
  type        = string
  description = "Optional existing bucket policy JSON to preserve current non-public statements."
  default     = ""
}

data "aws_iam_policy_document" "bucket_policy" {
  source_policy_documents = var.existing_bucket_policy_json == "" ? [] : [var.existing_bucket_policy_json]

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
}

resource "aws_s3_bucket_policy" "security_autopilot" {
  bucket = data.aws_s3_bucket.target.id
  policy = data.aws_iam_policy_document.bucket_policy.json
}

resource "aws_route53_record" "website_ipv4" {
  for_each = toset(var.aliases)
  zone_id  = var.route53_hosted_zone_id
  name     = each.value
  type     = "A"

  alias {
    name                   = aws_cloudfront_distribution.security_autopilot.domain_name
    zone_id                = aws_cloudfront_distribution.security_autopilot.hosted_zone_id
    evaluate_target_health = false
  }

  depends_on = [aws_s3_bucket_policy.security_autopilot]
}

resource "aws_route53_record" "website_ipv6" {
  for_each = toset(var.aliases)
  zone_id  = var.route53_hosted_zone_id
  name     = each.value
  type     = "AAAA"

  alias {
    name                   = aws_cloudfront_distribution.security_autopilot.domain_name
    zone_id                = aws_cloudfront_distribution.security_autopilot.hosted_zone_id
    evaluate_target_health = false
  }

  depends_on = [aws_s3_bucket_policy.security_autopilot]
}

resource "null_resource" "disable_bucket_website" {
  triggers = {
    bucket_name               = local.bucket_name
    remediation_region        = local.remediation_region
    website_configuration_sha = md5(var.existing_bucket_website_configuration_json)
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
aws s3api delete-bucket-website --bucket "${local.bucket_name}" --region "${local.remediation_region}"
EOT
  }

  depends_on = [
    aws_route53_record.website_ipv4,
    aws_route53_record.website_ipv6,
  ]
}

resource "aws_s3_bucket_public_access_block" "security_autopilot" {
  bucket = data.aws_s3_bucket.target.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  depends_on = [null_resource.disable_bucket_website]
}

output "cloudfront_distribution_id" {
  value       = aws_cloudfront_distribution.security_autopilot.id
  description = "CloudFront distribution ID."
}

output "cloudfront_domain_name" {
  value       = aws_cloudfront_distribution.security_autopilot.domain_name
  description = "Use this CloudFront domain or the configured aliases instead of the S3 website endpoint."
}

output "website_aliases" {
  value       = var.aliases
  description = "Aliases expected to resolve to the CloudFront distribution after Route53 cutover."
}
