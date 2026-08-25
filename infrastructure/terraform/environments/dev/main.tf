# Via infrastructure - Terraform scaffold.
#
# v0.1 provisions the durable state layer (DynamoDB single table, S3 media
# bucket with browser-upload CORS, EventBridge bus). Compute for the agent
# harness and workers lands with the first production deployment.

terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend: remote state per environment, e.g.:
  # backend "s3" {
  #   bucket = "via-tfstate"
  #   key    = "env/dev.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "via"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

module "core" {
  source = "../../modules/core"

  environment     = var.environment
  table_name      = var.table_name
  bucket_name     = var.bucket_name
  allowed_origins = var.allowed_origins
}
