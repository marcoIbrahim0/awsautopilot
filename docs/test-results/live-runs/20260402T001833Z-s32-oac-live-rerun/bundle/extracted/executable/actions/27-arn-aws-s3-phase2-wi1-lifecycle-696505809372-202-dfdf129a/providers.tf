# Configure AWS provider for account 696505809372 and region eu-north-1.
# Credentials: default chain (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, or ~/.aws/credentials [default]).
# If you use a named profile, add: profile = "your-profile-name" (do not use account ID as profile name).

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.100.0"
    }
    external = {
      source  = "hashicorp/external"
      version = "= 2.3.5"
    }
  }
}

provider "aws" {
  region = "eu-north-1"
}
