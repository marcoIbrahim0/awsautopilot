terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  name_prefix = var.name_prefix
  tags = merge(
    {
      Project = local.name_prefix
      Env     = var.app_env
    },
    var.tags
  )
}

