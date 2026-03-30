# S3 bucket access logging - Action: dcd9aac0-3205-4c1f-a360-8be492ac384f
# Remediation for: S3 general purpose buckets should have server access logging enabled
# Account: 696505809372 | Region: eu-north-1 | Bucket: security-autopilot-w6-envready-cloudtrail-696505809372
# Control: S3.9

variable "source_bucket_name" {
  type        = string
  description = "S3 source bucket where server access logging is enabled"
  default     = "security-autopilot-w6-envready-cloudtrail-696505809372"
}

variable "log_bucket_name" {
  type        = string
  description = "S3 bucket that will receive access logs"
  default     = "security-autopilot-access-logs-696505809372-s9fix1"
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
