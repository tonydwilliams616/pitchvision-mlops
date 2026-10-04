# -----------------------------------------------------------------------------
# AWS permissions for MLflow and External Secrets, via EKS Pod Identity.
# Each role can be assumed ONLY by one service account in one namespace,
# and grants only what that component needs. No access keys anywhere.
# The data itself (bucket, database, secret) lives in the permanent 18-data stack.
# -----------------------------------------------------------------------------
data "terraform_remote_state" "data" {
  backend = "s3"

  config = {
    bucket = "pitchvision-tfstate-352438994554"
    key    = "18-data/terraform.tfstate"
    region = "us-east-1"
  }
}

locals {
  artifacts_bucket_arn = data.terraform_remote_state.data.outputs.artifacts_bucket_arn
  db_secret_arn        = data.terraform_remote_state.data.outputs.db_master_secret_arn
}

# Shared trust policy: only the EKS Pod Identity service can assume these roles
data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

# --- MLflow: read/write the artifacts bucket --------------------------------
resource "aws_iam_role" "mlflow" {
  name               = "${var.project_name}-mlflow"
  description        = "MLflow tracking server - artifacts bucket access"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
}

data "aws_iam_policy_document" "mlflow" {
  statement {
    sid       = "ListArtifactsBucket"
    actions   = ["s3:ListBucket"]
    resources = [local.artifacts_bucket_arn]
  }

  statement {
    sid       = "ReadWriteArtifacts"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.artifacts_bucket_arn}/*"]
  }
}

resource "aws_iam_role_policy" "mlflow" {
  name   = "mlflow-artifacts"
  role   = aws_iam_role.mlflow.id
  policy = data.aws_iam_policy_document.mlflow.json
}

resource "aws_eks_pod_identity_association" "mlflow" {
  cluster_name    = local.cluster_name
  namespace       = "mlflow"
  service_account = "mlflow"
  role_arn        = aws_iam_role.mlflow.arn
}

# --- External Secrets: read the database secret, nothing else ---------------
resource "aws_iam_role" "external_secrets" {
  name               = "${var.project_name}-external-secrets"
  description        = "External Secrets Operator - read the MLflow database secret"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
}

data "aws_iam_policy_document" "external_secrets" {
  statement {
    sid       = "ReadMlflowDbSecret"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [local.db_secret_arn]
  }
}

resource "aws_iam_role_policy" "external_secrets" {
  name   = "read-mlflow-db-secret"
  role   = aws_iam_role.external_secrets.id
  policy = data.aws_iam_policy_document.external_secrets.json
}

resource "aws_eks_pod_identity_association" "external_secrets" {
  cluster_name    = local.cluster_name
  namespace       = "external-secrets"
  service_account = "external-secrets"
  role_arn        = aws_iam_role.external_secrets.arn
}
