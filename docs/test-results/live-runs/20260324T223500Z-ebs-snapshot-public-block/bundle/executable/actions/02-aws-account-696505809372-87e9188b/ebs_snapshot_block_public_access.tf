# EBS snapshot block public access - Action: 87e9188b-80ff-42cb-8e2a-e6b84eba1389
resource "aws_ebs_snapshot_block_public_access" "security_autopilot" {
  state = "block-all-sharing"
}
