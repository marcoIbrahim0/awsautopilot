# EBS snapshot block public access - Action: 12b5bacc-a721-4f05-afc1-2a7aed16048e
resource "aws_ebs_snapshot_block_public_access" "security_autopilot" {
  state = "block-all-sharing"
}
