# CloudTrail enabled - Action: 96c76e27-bffa-4979-86d4-719a97d7fcdc
# Remediation for: Enable CloudTrail
# Account: 029037611564 | Region: eu-north-1
# Control: CloudTrail.1
# Create an S3 bucket for trail logs and set trail_bucket_name below.

variable "trail_bucket_name" {
  type        = string
  description = "S3 bucket name for CloudTrail logs (create the bucket if it does not exist)"
}

variable "create_bucket_policy" {
  type        = bool
  default     = true
  description = "When true, create required CloudTrail S3 bucket policy statements."
}

resource "aws_cloudtrail" "security_autopilot" {
  name                          = "security-autopilot-trail"
  s3_bucket_name                = var.trail_bucket_name
  is_multi_region_trail          = true
  include_global_service_events = true
  enable_logging                = true
}

data "aws_iam_policy_document" "cloudtrail_bucket_policy" {
  statement {
    sid    = "AWSCloudTrailAclCheck"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions   = ["s3:GetBucketAcl"]
    resources = ["arn:aws:s3:::${var.trail_bucket_name}"]
  }

  statement {
    sid    = "AWSCloudTrailWrite"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions = ["s3:PutObject"]
    resources = [
      "arn:aws:s3:::${var.trail_bucket_name}/AWSLogs/029037611564/CloudTrail/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
  }
}

resource "aws_s3_bucket_policy" "cloudtrail_delivery" {
  count  = var.create_bucket_policy ? 1 : 0
  bucket = var.trail_bucket_name
  policy = data.aws_iam_policy_document.cloudtrail_bucket_policy.json
}

