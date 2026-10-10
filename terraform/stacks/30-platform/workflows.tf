# -----------------------------------------------------------------------------
# Argo Workflows S3 access, via Pod Identity. Workflow pods store step outputs
# (artifacts) and archived logs under the argo-workflows/ prefix of the
# permanent artifacts bucket; the Argo server reads them back for the UI.
# The role can touch ONLY that prefix - MLflow's area is out of reach.
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

locals {
  workflows_prefix    = "argo-workflows"
  datasets_bucket_arn = data.terraform_remote_state.data.outputs.datasets_bucket_arn
  # Bedrock model the match-summary step may call (cross-region inference profile)
  bedrock_model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

resource "aws_iam_role" "argo_workflows" {
  name               = "${var.project_name}-argo-workflows"
  description        = "Argo Workflows - artifacts and logs under the argo-workflows/ prefix"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
}

data "aws_iam_policy_document" "argo_workflows" {
  statement {
    sid       = "ListWorkflowsPrefix"
    actions   = ["s3:ListBucket"]
    resources = [local.artifacts_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.workflows_prefix}/*"]
    }
  }

  statement {
    sid       = "ReadWriteWorkflowsPrefix"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.artifacts_bucket_arn}/${local.workflows_prefix}/*"]
  }
  # Training jobs read datasets - read-only, never write
  statement {
    sid       = "ListDatasets"
    actions   = ["s3:ListBucket"]
    resources = [local.datasets_bucket_arn]
  }

  statement {
    sid       = "ReadDatasets"
    actions   = ["s3:GetObject"]
    resources = ["${local.datasets_bucket_arn}/*"]
  }
  # Match summaries: invoke ONE model, via its US inference profile. The profile
  # routes to the model in whichever US region has capacity, so both ARNs are needed.
  statement {
    sid     = "InvokeSummaryModel"
    actions = ["bedrock:InvokeModel"]
    resources = [
      "arn:aws:bedrock:us-east-1:${data.aws_caller_identity.current.account_id}:inference-profile/${local.bedrock_model_id}",
      "arn:aws:bedrock:*::foundation-model/${trimprefix(local.bedrock_model_id, "us.")}",
    ]
  }
}

resource "aws_iam_role_policy" "argo_workflows" {
  name   = "argo-workflows-artifacts"
  role   = aws_iam_role.argo_workflows.id
  policy = data.aws_iam_policy_document.argo_workflows.json
}

# Workflow pods (they write artifacts and logs)
resource "aws_eks_pod_identity_association" "argo_workflow_pods" {
  cluster_name    = local.cluster_name
  namespace       = "workflows"
  service_account = "argo-workflow"
  role_arn        = aws_iam_role.argo_workflows.arn
}

# Argo server (reads artifacts and logs back for the UI)
resource "aws_eks_pod_identity_association" "argo_workflows_server" {
  cluster_name    = local.cluster_name
  namespace       = "argo"
  service_account = "argo-workflows-server"
  role_arn        = aws_iam_role.argo_workflows.arn
}
