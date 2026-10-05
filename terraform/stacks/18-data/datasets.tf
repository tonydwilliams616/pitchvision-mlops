# -----------------------------------------------------------------------------
# Training datasets, versioned by path: <dataset>/<version>/{train,valid,test}
# plus a manifest.json recording source, licence and contents. A dataset
# version is never overwritten - a new version gets a new path.
# Separate from the MLflow artifacts bucket so access can differ (training
# jobs read datasets but never write them).
# -----------------------------------------------------------------------------
locals {
  datasets_bucket_name = "${var.project_name}-datasets-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "datasets" {
  #checkov:skip=CKV_AWS_144:Cross-region replication not needed for a portfolio project
  #checkov:skip=CKV_AWS_18:Access logging not needed for a single-user bucket
  #checkov:skip=CKV2_AWS_62:Event notifications not needed
  #checkov:skip=CKV_AWS_145:SSE-S3 is sufficient; avoids KMS key cost
  bucket = local.datasets_bucket_name

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "datasets" {
  bucket = aws_s3_bucket.datasets.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "datasets" {
  bucket = aws_s3_bucket.datasets.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "datasets" {
  bucket = aws_s3_bucket.datasets.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "datasets" {
  bucket = aws_s3_bucket.datasets.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "datasets" {
  bucket = aws_s3_bucket.datasets.id

  rule {
    id     = "expire-old-object-versions"
    status = "Enabled"

    filter {}

    # Safety net against accidental overwrites/deletes, without keeping
    # superseded copies forever
    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "aws_iam_policy_document" "datasets" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.datasets.arn,
      "${aws_s3_bucket.datasets.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "datasets" {
  bucket = aws_s3_bucket.datasets.id
  policy = data.aws_iam_policy_document.datasets.json

  depends_on = [aws_s3_bucket_public_access_block.datasets]
}

output "datasets_bucket_name" {
  description = "S3 bucket for versioned training datasets."
  value       = aws_s3_bucket.datasets.id
}

output "datasets_bucket_arn" {
  description = "ARN of the datasets bucket - used for training job read access."
  value       = aws_s3_bucket.datasets.arn
}
