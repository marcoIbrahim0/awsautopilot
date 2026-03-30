# S3 bucket access logging - Action: 01557e04-8980-4554-8c32-5a7e78d3cbf3
# Remediation for: S3 general purpose buckets should have server access logging enabled
# Account: 696505809372 | Region: eu-north-1 | Bucket: config-bucket-696505809372
# Control: S3.9

variable "source_bucket_name" {
  type        = string
  description = "S3 source bucket where server access logging is enabled"
  default     = "config-bucket-696505809372"
}

variable "log_bucket_name" {
  type        = string
  description = "S3 bucket that will receive access logs"
  default     = "security-autopilot-access-logs-696505809372-r221001"
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
