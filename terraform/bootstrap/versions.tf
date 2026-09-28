terraform {
  required_version = ">= 1.10" # needed for S3 native state locking (use_lockfile)

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # No backend block on first apply - state starts local, then gets migrated
  # into the bucket this stack creates. See README.md.
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project    = var.project_name
      ManagedBy  = "terraform"
      Stack      = "bootstrap"
      Repository = "${var.github_owner}/${var.github_repo}"
    }
  }
}
