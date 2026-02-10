terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "region" {
  description = "AWS region where the security group is created."
  type        = string
  default     = "eu-north-1"
}

variable "vpc_id" {
  description = "Optional VPC ID. If empty, default VPC is used."
  type        = string
  default     = ""
}

variable "security_group_name" {
  description = "Name for the intentionally vulnerable security group."
  type        = string
  default     = "security-autopilot-ec2-53-vulnerable"
}

provider "aws" {
  region = var.region
}

data "aws_vpc" "default" {
  count   = var.vpc_id == "" ? 1 : 0
  default = true
}

locals {
  selected_vpc_id = var.vpc_id != "" ? var.vpc_id : data.aws_vpc.default[0].id
}

resource "aws_security_group" "vulnerable" {
  name        = var.security_group_name
  description = "Intentionally vulnerable SG for EC2.53 test findings."
  vpc_id      = local.selected_vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "ssh_anywhere" {
  security_group_id = aws_security_group.vulnerable.id
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "rdp_anywhere" {
  security_group_id = aws_security_group.vulnerable.id
  ip_protocol       = "tcp"
  from_port         = 3389
  to_port           = 3389
  cidr_ipv4         = "0.0.0.0/0"
}

output "vulnerable_security_group_id" {
  value = aws_security_group.vulnerable.id
}
