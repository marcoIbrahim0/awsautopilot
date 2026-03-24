# Configure AWS provider with credentials for account 696505809372.
# Account-level S3 Block Public Access uses S3 Control API; region is not required for this resource.

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.100.0"
    }
  }
}

# provider "aws" {
#   region = "us-east-1"  # Optional; account-level block applies to all regions
# }
