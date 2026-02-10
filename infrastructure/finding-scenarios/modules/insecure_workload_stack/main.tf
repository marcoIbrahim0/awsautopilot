terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "name_prefix" {
  description = "Prefix used for named resources."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for the intentionally vulnerable workload host."
  type        = string
}

variable "region" {
  description = "AWS region for CLI-backed EC2 account settings."
  type        = string
}

locals {
  sanitized_prefix = trim(substr(replace(lower(var.name_prefix), "_", "-"), 0, 24), "-")

  workload_tags = {
    Environment = "test-insecure"
    Purpose     = "security-hub-finding-generation"
    ManagedBy   = "terraform"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_vpc" "workload" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.workload_tags, { Name = "${local.sanitized_prefix}-vpc" })
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.workload.id
  cidr_block              = "10.42.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags                    = merge(local.workload_tags, { Name = "${local.sanitized_prefix}-public-a" })
}

resource "aws_internet_gateway" "workload" {
  vpc_id = aws_vpc.workload.id
  tags   = merge(local.workload_tags, { Name = "${local.sanitized_prefix}-igw" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.workload.id
  tags   = merge(local.workload_tags, { Name = "${local.sanitized_prefix}-public-rt" })
}

resource "aws_route" "default_egress" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.workload.id
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "admin_ports_open" {
  name        = "${local.sanitized_prefix}-admin-sg"
  description = "Intentionally vulnerable: admin ports open to the internet."
  vpc_id      = aws_vpc.workload.id
  tags        = merge(local.workload_tags, { Name = "${local.sanitized_prefix}-admin-sg" })
}

resource "aws_vpc_security_group_ingress_rule" "ssh_from_anywhere" {
  security_group_id = aws_security_group.admin_ports_open.id
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "rdp_from_anywhere" {
  security_group_id = aws_security_group.admin_ports_open.id
  ip_protocol       = "tcp"
  from_port         = 3389
  to_port           = 3389
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "egress_all" {
  security_group_id = aws_security_group.admin_ports_open.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_s3_account_public_access_block" "account_level_off" {
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket" "public_assets" {
  bucket_prefix = "${local.sanitized_prefix}-pub-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "public_assets" {
  bucket = aws_s3_bucket.public_assets.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "public_assets" {
  bucket = aws_s3_bucket.public_assets.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowPublicReadObjects"
        Effect    = "Allow"
        Principal = "*"
        Action    = ["s3:GetObject"]
        Resource  = "${aws_s3_bucket.public_assets.arn}/*"
      }
    ]
  })

  depends_on = [
    aws_s3_account_public_access_block.account_level_off,
    aws_s3_bucket_public_access_block.public_assets,
  ]
}

resource "aws_s3_bucket" "transport_policy_missing_ssl_deny" {
  bucket_prefix = "${local.sanitized_prefix}-nossl-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "transport_policy_missing_ssl_deny" {
  bucket = aws_s3_bucket.transport_policy_missing_ssl_deny.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "transport_policy_missing_ssl_deny" {
  bucket = aws_s3_bucket.transport_policy_missing_ssl_deny.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowWorkloadRoleReadWrite"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.workload_ec2.arn
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.transport_policy_missing_ssl_deny.arn,
          "${aws_s3_bucket.transport_policy_missing_ssl_deny.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_s3_bucket" "unencrypted_default" {
  bucket_prefix = "${local.sanitized_prefix}-unencr-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "unencrypted_default" {
  bucket = aws_s3_bucket.unencrypted_default.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "sse_s3_only" {
  bucket_prefix = "${local.sanitized_prefix}-sse3-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "sse_s3_only" {
  bucket = aws_s3_bucket.sse_s3_only.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "sse_s3_only" {
  bucket = aws_s3_bucket.sse_s3_only.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket" "no_access_logging" {
  bucket_prefix = "${local.sanitized_prefix}-nolog-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "no_access_logging" {
  bucket = aws_s3_bucket.no_access_logging.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "no_lifecycle" {
  bucket_prefix = "${local.sanitized_prefix}-nolife-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "no_lifecycle" {
  bucket = aws_s3_bucket.no_lifecycle.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_ebs_encryption_by_default" "disabled" {
  enabled = false
}

resource "terraform_data" "disable_snapshot_block_public_access" {
  input = {
    region = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command     = <<BASH
set -euo pipefail
export AWS_DEFAULT_REGION="${var.region}"
aws ec2 disable-snapshot-block-public-access >/dev/null
state=$(aws ec2 get-snapshot-block-public-access-state --query 'State' --output text 2>/dev/null || echo "unknown")
echo "EBS snapshot block public access state in ${var.region}: $state"
BASH
  }
}

resource "aws_iam_role" "workload_ec2" {
  name = "${local.sanitized_prefix}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "workload_bucket_access" {
  name = "${local.sanitized_prefix}-bucket-access"
  role = aws_iam_role.workload_ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.public_assets.arn,
          "${aws_s3_bucket.public_assets.arn}/*",
          aws_s3_bucket.transport_policy_missing_ssl_deny.arn,
          "${aws_s3_bucket.transport_policy_missing_ssl_deny.arn}/*",
          aws_s3_bucket.unencrypted_default.arn,
          "${aws_s3_bucket.unencrypted_default.arn}/*",
          aws_s3_bucket.sse_s3_only.arn,
          "${aws_s3_bucket.sse_s3_only.arn}/*",
          aws_s3_bucket.no_access_logging.arn,
          "${aws_s3_bucket.no_access_logging.arn}/*",
          aws_s3_bucket.no_lifecycle.arn,
          "${aws_s3_bucket.no_lifecycle.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "workload_ec2" {
  name = "${local.sanitized_prefix}-ec2-profile"
  role = aws_iam_role.workload_ec2.name
}

resource "aws_instance" "workload" {
  ami                    = data.aws_ssm_parameter.al2023_ami.value
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public_a.id
  vpc_security_group_ids = [aws_security_group.admin_ports_open.id]
  iam_instance_profile   = aws_iam_instance_profile.workload_ec2.name

  root_block_device {
    encrypted   = false
    volume_size = 10
  }

  user_data = <<EOF
#!/bin/bash
echo "insecure workload node" > /tmp/security-autopilot.txt
echo "${aws_s3_bucket.public_assets.id}" >> /tmp/security-autopilot.txt
echo "${aws_s3_bucket.unencrypted_default.id}" >> /tmp/security-autopilot.txt
EOF

  depends_on = [aws_ebs_encryption_by_default.disabled]
  tags       = merge(local.workload_tags, { Name = "${local.sanitized_prefix}-ec2" })
}

resource "aws_ebs_volume" "workload_data" {
  availability_zone = aws_subnet.public_a.availability_zone
  size              = 8
  type              = "gp3"
  encrypted         = false
  tags              = merge(local.workload_tags, { Name = "${local.sanitized_prefix}-data-volume" })
}

resource "aws_volume_attachment" "workload_data" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.workload_data.id
  instance_id = aws_instance.workload.id
}

resource "aws_ebs_snapshot" "workload_data" {
  volume_id = aws_ebs_volume.workload_data.id
  tags      = merge(local.workload_tags, { Name = "${local.sanitized_prefix}-data-snapshot" })

  depends_on = [terraform_data.disable_snapshot_block_public_access]
}

resource "terraform_data" "make_snapshot_public" {
  input = {
    snapshot_id = aws_ebs_snapshot.workload_data.id
    region      = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command     = <<BASH
set -euo pipefail
export AWS_DEFAULT_REGION="${var.region}"
aws ec2 modify-snapshot-attribute \
  --snapshot-id "${aws_ebs_snapshot.workload_data.id}" \
  --attribute createVolumePermission \
  --operation-type add \
  --group-names all \
  >/dev/null
echo "Snapshot ${aws_ebs_snapshot.workload_data.id} is publicly shareable."
BASH
  }

  depends_on = [aws_ebs_snapshot.workload_data]
}

output "architecture_name" {
  value = "insecure_workload_stack"
}

output "ec2_instance_id" {
  value = aws_instance.workload.id
}

output "workload_iam_role_name" {
  value = aws_iam_role.workload_ec2.name
}

output "open_admin_security_group_id" {
  value = aws_security_group.admin_ports_open.id
}

output "workload_snapshot_id" {
  value = terraform_data.make_snapshot_public.input.snapshot_id
}

output "bucket_names" {
  value = {
    public_assets                     = aws_s3_bucket.public_assets.id
    transport_policy_missing_ssl_deny = aws_s3_bucket.transport_policy_missing_ssl_deny.id
    unencrypted_default               = aws_s3_bucket.unencrypted_default.id
    sse_s3_only                       = aws_s3_bucket.sse_s3_only.id
    no_access_logging                 = aws_s3_bucket.no_access_logging.id
    no_lifecycle                      = aws_s3_bucket.no_lifecycle.id
  }
}
