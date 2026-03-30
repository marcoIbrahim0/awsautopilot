# EBS default encryption - Action: cdbe5eda-ae70-4d31-815c-35fce06c1596
resource "aws_ebs_encryption_by_default" "security_autopilot" {
  enabled = true
}

