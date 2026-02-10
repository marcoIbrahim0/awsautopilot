terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

module "foundational_controls_gaps" {
  source = "../../modules/foundational_controls_gaps"

  region      = var.region
  name_prefix = "${var.name_prefix}-foundation"
}

module "insecure_workload_stack" {
  source = "../../modules/insecure_workload_stack"

  name_prefix   = "${var.name_prefix}-workload"
  instance_type = var.instance_type
  region        = var.region
}
