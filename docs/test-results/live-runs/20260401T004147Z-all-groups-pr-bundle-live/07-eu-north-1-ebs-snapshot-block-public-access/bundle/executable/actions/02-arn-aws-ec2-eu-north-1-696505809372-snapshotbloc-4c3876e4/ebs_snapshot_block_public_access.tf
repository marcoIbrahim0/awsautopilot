# EBS snapshot block public access - Action: 4c3876e4-8260-4897-a8a4-4fb7f683d357
resource "aws_ebs_snapshot_block_public_access" "security_autopilot" {
  state = "block-all-sharing"
}
