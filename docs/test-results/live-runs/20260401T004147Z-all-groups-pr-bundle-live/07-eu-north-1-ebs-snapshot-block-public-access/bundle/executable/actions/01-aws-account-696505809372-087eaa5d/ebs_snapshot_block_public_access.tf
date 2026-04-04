# EBS snapshot block public access - Action: 087eaa5d-4fdf-4139-9b4c-104de2608fbb
resource "aws_ebs_snapshot_block_public_access" "security_autopilot" {
  state = "block-all-sharing"
}
