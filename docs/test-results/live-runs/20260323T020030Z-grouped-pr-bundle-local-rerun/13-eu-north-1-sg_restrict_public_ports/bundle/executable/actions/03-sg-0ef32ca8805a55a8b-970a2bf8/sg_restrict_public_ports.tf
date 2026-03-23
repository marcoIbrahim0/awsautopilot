# SG restrict public ports (22/3389) - Action: 970a2bf8-e01b-4a2c-a699-cec968652acb
# Remediation for: Security groups should only allow unrestricted incoming traffic for authorized ports
# Account: 696505809372 | Region: eu-north-1 | Security group: sg-0ef32ca8805a55a8b
# Control: EC2.53
# Safe rollout: identify SG attachments and active traffic first; tighten incrementally and test after each change.
# Prefer replacing broad sources (0.0.0.0/0 or ::/0) with VPN/office CIDR or source security-group rules.

variable "security_group_id" {
  type        = string
  default     = "sg-0ef32ca8805a55a8b"
  description = "Security group ID to restrict"
}

variable "allowed_cidr" {
  type        = string
  default     = "10.0.0.0/8"
  description = "CIDR allowed for SSH/RDP (e.g. VPN or bastion)"
}

variable "allowed_cidr_ipv6" {
  type        = string
  default     = ""
  description = "Optional IPv6 CIDR allowed for SSH/RDP (e.g. fd00::/8). Leave empty to skip IPv6 ingress."
}

variable "remove_existing_public_rules" {
  type        = bool
  default     = false
  description = "When true, revoke existing public SSH/RDP ingress (0.0.0.0/0 and ::/0) before adding restricted rules."
}

variable "remediation_region" {
  type        = string
  default     = "eu-north-1"
  description = "Region used by local AWS CLI revoke commands."
}

resource "null_resource" "revoke_public_admin_ingress" {
  count = var.remove_existing_public_rules == true ? 1 : 0

  triggers = {
    security_group_id = var.security_group_id
    region            = var.remediation_region
    allowed_cidr      = var.allowed_cidr
    allowed_cidr_ipv6 = var.allowed_cidr_ipv6
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set +e
aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=0.0.0.0/0}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,IpRanges=[{CidrIp=0.0.0.0/0}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,Ipv6Ranges=[{CidrIpv6=::/0}]' >/dev/null 2>&1 || true
aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,Ipv6Ranges=[{CidrIpv6=::/0}]' >/dev/null 2>&1 || true
if [ -n "${var.allowed_cidr}" ]; then
  aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=${var.allowed_cidr}}]' >/dev/null 2>&1 || true
  aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,IpRanges=[{CidrIp=${var.allowed_cidr}}]' >/dev/null 2>&1 || true
fi
if [ -n "${var.allowed_cidr_ipv6}" ]; then
  aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,Ipv6Ranges=[{CidrIpv6=${var.allowed_cidr_ipv6}}]' >/dev/null 2>&1 || true
  aws ec2 revoke-security-group-ingress --region "${var.remediation_region}" --group-id "${var.security_group_id}" --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,Ipv6Ranges=[{CidrIpv6=${var.allowed_cidr_ipv6}}]' >/dev/null 2>&1 || true
fi
exit 0
EOT
  }
}

resource "aws_vpc_security_group_ingress_rule" "ssh_restricted" {
  security_group_id = var.security_group_id
  cidr_ipv4         = var.allowed_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  description       = "SSH from allowed CIDR - Security Autopilot"
  depends_on        = [null_resource.revoke_public_admin_ingress]
}

resource "aws_vpc_security_group_ingress_rule" "rdp_restricted" {
  security_group_id = var.security_group_id
  cidr_ipv4         = var.allowed_cidr
  from_port         = 3389
  to_port           = 3389
  ip_protocol       = "tcp"
  description       = "RDP from allowed CIDR - Security Autopilot"
  depends_on        = [null_resource.revoke_public_admin_ingress]
}

resource "aws_vpc_security_group_ingress_rule" "ssh_restricted_ipv6" {
  count             = var.allowed_cidr_ipv6 != "" ? 1 : 0
  security_group_id = var.security_group_id
  cidr_ipv6         = var.allowed_cidr_ipv6
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  description       = "SSH from allowed IPv6 CIDR - Security Autopilot"
  depends_on        = [null_resource.revoke_public_admin_ingress]
}

resource "aws_vpc_security_group_ingress_rule" "rdp_restricted_ipv6" {
  count             = var.allowed_cidr_ipv6 != "" ? 1 : 0
  security_group_id = var.security_group_id
  cidr_ipv6         = var.allowed_cidr_ipv6
  from_port         = 3389
  to_port           = 3389
  ip_protocol       = "tcp"
  description       = "RDP from allowed IPv6 CIDR - Security Autopilot"
  depends_on        = [null_resource.revoke_public_admin_ingress]
}
