# SG replace public admin ingress with bastion SG references - Action: dfa0a526-87b8-4670-92d7-401a611f58f5
# Remediation for: Security groups should not allow ingress from 0.0.0.0/0 or ::/0 to port 22
# Account: 696505809372 | Region: eu-north-1 | Security group: sg-0ef32ca8805a55a8b
# Control: EC2.53
# Requires operator access to move through approved bastion security groups before apply.
# This bundle removes public SSH/RDP ingress and replaces it with source-security-group rules from the approved bastion list.

variable "security_group_id" {
  type        = string
  default     = "sg-0ef32ca8805a55a8b"
  description = "Security group ID to harden for bastion-based operator access"
}

variable "approved_bastion_security_group_ids" {
  type        = list(string)
  default     = ["sg-085d69a76707542b2"]
  description = "Approved bastion security group IDs that may retain SSH/RDP access"
}

variable "remediation_region" {
  type        = string
  default     = "eu-north-1"
  description = "Region used by local AWS CLI revoke commands."
}

locals {
  bastion_security_group_ids = toset(var.approved_bastion_security_group_ids)
}

resource "null_resource" "revoke_public_admin_ingress" {
  triggers = {
    security_group_id = var.security_group_id
    region            = var.remediation_region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set +e
aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=0.0.0.0/0}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,IpRanges=[{CidrIp=0.0.0.0/0}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,Ipv6Ranges=[{CidrIpv6=::/0}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,Ipv6Ranges=[{CidrIpv6=::/0}]' >/dev/null 2>&1 || true
exit 0
EOT
  }
}

resource "aws_vpc_security_group_ingress_rule" "bastion_ssh" {
  for_each                      = local.bastion_security_group_ids
  security_group_id            = var.security_group_id
  referenced_security_group_id = each.value
  from_port                    = 22
  to_port                      = 22
  ip_protocol                  = "tcp"
  description                  = "SSH from approved bastion security group ${each.value} - Security Autopilot"
  depends_on                   = [null_resource.revoke_public_admin_ingress]
}

resource "aws_vpc_security_group_ingress_rule" "bastion_rdp" {
  for_each                      = local.bastion_security_group_ids
  security_group_id            = var.security_group_id
  referenced_security_group_id = each.value
  from_port                    = 3389
  to_port                      = 3389
  ip_protocol                  = "tcp"
  description                  = "RDP from approved bastion security group ${each.value} - Security Autopilot"
  depends_on                   = [null_resource.revoke_public_admin_ingress]
}
