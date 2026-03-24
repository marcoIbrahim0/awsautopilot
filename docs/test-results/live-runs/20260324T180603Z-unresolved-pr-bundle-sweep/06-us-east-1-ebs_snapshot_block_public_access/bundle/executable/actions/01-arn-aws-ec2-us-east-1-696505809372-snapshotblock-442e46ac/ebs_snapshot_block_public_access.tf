# EBS snapshot block public access - Action: 442e46ac-f31c-4242-82ca-9e47081a3adb
resource "aws_ebs_snapshot_block_public_access" "security_autopilot" {
  state = "block-all-sharing"
}
