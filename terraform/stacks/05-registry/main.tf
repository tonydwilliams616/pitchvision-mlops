# -----------------------------------------------------------------------------
# PERSISTENT container registry. Images survive cluster teardowns, so every
# trained model can be traced back to the exact image that produced it.
# -----------------------------------------------------------------------------
locals {
  # Training images are ~3.3 GB each, so keep only a few
  ecr_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the 5 most recent images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = { type = "expire" }
      },
    ]
  })
}

resource "aws_ecr_repository" "training" {
  #checkov:skip=CKV_AWS_136:AES256 is sufficient; avoids KMS key cost
  name = "${var.project_name}/training"

  # Tags are Git commit SHAs and can never be overwritten: a tag always means
  # exactly one image, which is what makes lineage trustworthy
  image_tag_mutability = "IMMUTABLE"

  # Free basic vulnerability scan of every pushed image
  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "training" {
  repository = aws_ecr_repository.training.name
  policy     = local.ecr_lifecycle_policy
}

# Inference service image (serves the @champion model)
resource "aws_ecr_repository" "inference" {
  #checkov:skip=CKV_AWS_136:AES256 is sufficient; avoids KMS key cost
  name                 = "${var.project_name}/inference"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "inference" {
  repository = aws_ecr_repository.inference.name
  policy     = local.ecr_lifecycle_policy
}