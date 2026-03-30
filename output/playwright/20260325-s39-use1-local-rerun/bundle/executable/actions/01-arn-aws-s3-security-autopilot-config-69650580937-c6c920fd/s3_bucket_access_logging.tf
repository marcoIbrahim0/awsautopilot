# S3 bucket access logging - Action: c6c920fd-b9f6-4015-8ede-a072d5ad22c5
# Remediation for: S3 general purpose buckets should have server access logging enabled
# Account: 696505809372 | Region: us-east-1 | Bucket: security-autopilot-config-696505809372-us-east-1
# Control: S3.9

variable "source_bucket_name" {
  type        = string
  description = "S3 source bucket where server access logging is enabled"
  default     = "security-autopilot-config-696505809372-us-east-1"
}

variable "log_bucket_name" {
  type        = string
  description = "S3 bucket that will receive access logs"
  default     = "sa-access-logs-696505809372-use1-r0325224512"
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
