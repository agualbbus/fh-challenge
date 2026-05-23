terraform {
  required_version = ">= 1.5.0"

  required_providers {
    temporalcloud = {
      source  = "temporalio/temporalcloud"
      version = "~> 1.3.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.46.0"
    }
  }
}

provider "temporalcloud" {
  # TEMPORAL_CLOUD_API_KEY from shell env (never commit)
  allowed_account_id = var.temporal_account_id != "" ? var.temporal_account_id : null
}

provider "aws" {
  region = var.aws_region
}
