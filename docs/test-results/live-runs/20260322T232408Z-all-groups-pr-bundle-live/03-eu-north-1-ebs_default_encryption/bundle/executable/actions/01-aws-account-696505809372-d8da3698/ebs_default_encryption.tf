# EBS default encryption - Action: d8da3698-230f-44e3-9c11-cc9e4099b7f6
resource "aws_ebs_encryption_by_default" "security_autopilot" {
  enabled = true
}

