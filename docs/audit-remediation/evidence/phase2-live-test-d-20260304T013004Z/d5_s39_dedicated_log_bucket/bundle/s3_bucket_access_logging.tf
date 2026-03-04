# S3 bucket access logging - Action: fb8e7dcb-2acb-49df-84e1-09ff82bf8015
# Remediation for: S3.9 access logging (Live Test D5)
# Account: 029037611564 | Region: eu-north-1 | Bucket: sa-live-d5-src-029037611564-0304014445
# Control: S3.9

variable "source_bucket_name" {
  type        = string
  description = "S3 source bucket where server access logging is enabled"
  default     = "sa-live-d5-src-029037611564-0304014445"
}

variable "log_bucket_name" {
  type        = string
  description = "S3 bucket that will receive access logs"
  default     = "sa-live-d5-log-029037611564-0304014445"
}

variable "log_prefix" {
  type        = string
  description = "Prefix for delivered access logs"
  default     = "s3-access-logs/"
}

resource "aws_s3_bucket_logging" "security_autopilot" {
  bucket        = var.source_bucket_name
  target_bucket = var.log_bucket_name
  target_prefix = var.log_prefix
}
