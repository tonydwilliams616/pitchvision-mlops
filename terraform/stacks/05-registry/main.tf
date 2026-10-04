# -----------------------------------------------------------------------------
# PERSISTENT container registry. Images survive cluster teardowns, so every
# trained model can be traced back to the exact image that produced it.
# -----------------------------------------------------------------------------
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

# Storage costs ~$0.10/GB-month and training images are several GB, so only
# keep recent ones
resource "aws_ecr_lifecycle_policy" "training" {
  repository = aws_ecr_repository.training.name

  policy = jsonencode({
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
        description  = "Keep only the 20 most recent images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 20
        }
        action = { type = "expire" }
      },
    ]
  })
}
