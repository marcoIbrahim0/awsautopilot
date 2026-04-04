# EBS default encryption - Action: c400ae42-865c-4808-8aa0-11450b717714
resource "aws_ebs_encryption_by_default" "security_autopilot" {
  enabled = true
}

