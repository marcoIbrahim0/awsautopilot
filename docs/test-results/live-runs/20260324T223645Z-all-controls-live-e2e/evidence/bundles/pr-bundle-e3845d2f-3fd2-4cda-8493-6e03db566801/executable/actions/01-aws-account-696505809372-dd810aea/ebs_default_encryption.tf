# EBS default encryption - Action: dd810aea-8c89-4782-8e1f-2d2140e9c08d
resource "aws_ebs_encryption_by_default" "security_autopilot" {
  enabled = true
}

