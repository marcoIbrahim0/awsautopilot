# SG remove public admin ingress for SSM-only access - Action: 58a22607-666e-4016-8fe3-4ce62a235a6e
# Remediation for: Security groups should only allow unrestricted incoming traffic for authorized ports
# Account: 696505809372 | Region: eu-north-1 | Security group: sg-06f6252fa8a95b61d
# Control: EC2.53
# Requires operator access to already be available through SSM Session Manager before apply.
# This bundle removes public SSH/RDP ingress and intentionally does not add replacement SSH/RDP rules.

variable "security_group_id" {
  type        = string
  default     = "sg-06f6252fa8a95b61d"
  description = "Security group ID to harden for SSM-only operator access"
}

variable "remediation_region" {
  type        = string
  default     = "eu-north-1"
  description = "Region used by local AWS CLI revoke commands."
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
